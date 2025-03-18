/*
 * WFCATALOG Webservice NodeJS Implementation 3.0
 * Written for Node, Express, and MongoDB
 *
 * Installation: npm install, npm test, npm start
 *
 *
 * Author: Mathijs Koymans (koymans@knmi.nl)
 * Jollyfant @ GitHub
 * Last Updated: 2016-09-07
 *
 * This application is designed after the WFCatalog Specifications, version 0.3.0
 *
 *   Routes and Middleware functions:
 *   ? indicates one middleware function (GET/POST) of the same level
 *
 *   [MWID0] (*) disables CORS headers
 *
 *   [MWID1] (/wfcatalog/1/version) returns version application
 *
 *   [MWID2] (/wfcatalog/1/application.wadl) returns application.wadl
 *
 *   [MWID3] (/wfcatalog/1/query) handles WFCatalog database request
 *
 *   ? [MWID3.1.A1] Sanity check on GET request
 *
 *       [MWID3.1.A2] parses GET request
 *
 *   ? [MWID3.1.B1]  Obtains body from POST request
 *
 *       [MWID3.1.B2] Sanity check and parses POST request
 *
 *         [MWID3.2] validate sanity of start & end times
 *
 *           [MWID3.3] set user request options
 *
 *             [MWID3.4] sanitize and prepares DB query
 *
 *               [MWID3.5] handles DB request and response stream
 *
 */

/*
 * Wrap in a module export to be used with cluster.js
 * pass a JSON dictionary of configuration options (see configuration.json)
 * It is possible to pass a callback that is fired after the service has begun listening
 */
module.exports = function (CONFIG, WFCatalogCallback) {
  "use strict";

  // Static utilities used by the service
  var ERROR = require("./static/errors");
  var DB_MAP = require("./static/dbmap");
  var CLIENT_MAP = swapMap(DB_MAP);
  var TYPES = require("./static/types");
  var METRICS = require("./static/metrics.json");

  var REGEX_TABLE = compileRegexTable(); // Regex database to check types against

  // Load the MongoDB module
  var MongoClient = require("mongodb").MongoClient;
  var ObjectId = require("mongodb").ObjectID;

  var WFCatalogger;
  setupLogger();

  // The service is powered by express
  var WFCatalog = require("express")();

  /*
   * WFCatalog Middleware [MWID0]
   * Allow Cross Origin from anywhere
   */
  WFCatalog.all(CONFIG.BASE_URL + "*", function (req, res, next) {
    // 404 default favicon requests made by Chrome
    if (req.url === "./favicon.ico") {
      return res.status(404).end();
    }

    // Enable CORS headers and proceed to the next middleware
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Headers", "X-Requested-With");

    next();
  });

  // Root implementation
  WFCatalog.get(CONFIG.BASE_URL, function (req, res, next) {
    if (req.url.substr(-1) !== "/") {
      res.redirect(301, req.url + "/");
    } else {
      res.setHeader("Content-Type", "text/html");
      res.status(200).sendFile(__dirname + "/root.html");
    }
  });

  /*
   * WFCatalog version implementation [MWID1]
   * Serve the configured webservice version
   */
  WFCatalog.get(CONFIG.BASE_URL + "version", function (req, res, next) {
    res.setHeader("Content-Type", "text/plain");
    res.status(200).send(CONFIG.VERSION);
  });

  /*
   * WFCatalog WADL implementation [MWID2]
   * Serves the static application.wadl
   */
  WFCatalog.get(
    CONFIG.BASE_URL + "application.wadl",
    function (req, res, next) {
      res.setHeader("Content-Type", "application/xml");
      res.status(200).sendFile(__dirname + "/application.wadl");
    },
  );

  /*
   * WFCatalog query implementation [MWID3]
   * Serves database response to given request
   */
  WFCatalog.all(CONFIG.BASE_URL + "query", function (req, res, next) {
    res.setHeader("Content-Type", "text/plain");

    // Set initial request options
    req.WFCatalog = {
      connected: true,
      requestId: getRequestId(),
      requestSubmitted: new Date(),
    };

    // The service is closed for maintenance; abort
    if (CONFIG.CLOSED) {
      return sendErrorPage(req, res, ERROR.SERVICE_CLOSED);
    }

    // The database connection failed, try to reconnect
    if (!Mongo) {
      connect_to_mongo();
      return sendErrorPage(req, res, ERROR.MONGO_CONNECTION_FAILED);
    }

    // When the user disconnects, update so that we can kill
    // any remaining database work
    res.on("close", function () {
      req.WFCatalog.connected = false;
    });

    /*
     * Log the request summary on a succesful request
     */
    res.on("finish", function () {
      if (req.WFCatalog.nDocuments) {
        var nDocuments = req.WFCatalog.nDocuments;
        var nBytes = req.WFCatalog.nBytes;
      }

      // Log finished HTTP request
      WFCatalogger.info(
        {
          code: res.statusCode,
          client:
            req.headers["x-forwarded-for"] || req.connection.remoteAddress,
          message: res.statusMessage,
          method: req.method,
          id: req.WFCatalog.requestId,
          worker: CONFIG.WORKER,
          nSegments: req.WFCatalog.nSegments || 0,
          nDocuments: nDocuments || 0,
          nBytes: nBytes || 0,
          nContinuous: req.WFCatalog.nContinuous || 0,
          msQueryTime: req.WFCatalog.msQueryTime || 0,
          msTotalRequestTime: Date.now() - req.WFCatalog.requestSubmitted,
        },
        "HTTP request summary",
      );
    });

    next();
  });

  /*
   * WFCatalog query GET implementation [MWID3.1.A1]
   */
  WFCatalog.get(CONFIG.BASE_URL + "query", function (req, res, next) {
    // Check if the query is empty
    if (!req._parsedUrl.search) {
      return sendErrorPage(req, res, ERROR.EMPTY_QUERY);
    }

    // Check if the query exceeds the maximum query length (in bytes)
    if (Buffer.byteLength(req._parsedUrl.search) > CONFIG.MAXIMUM_GET_BYTES) {
      return sendErrorPage(req, res, ERROR.QUERY_LENGTH_EXCEEDED);
    }

    // Rough check on the query format
    if (!REGEX_TABLE.query.test(req._parsedUrl.search)) {
      return sendErrorPage(req, res, ERROR.INVALID_QUERY);
    }

    req.WFCatalog.query = new Object();

    // Go over all keys and get the corresponding database key
    for (var key in req.query) {
      var databaseKey = getDatabaseKey(key);

      // If the return of this function is null
      // the key is not allowed, throw 400
      if (!databaseKey) {
        return sendErrorPage(req, res, ERROR.INVALID_PARAMETER_GET, key);
      }

      // Double specified parameters become an array of values
      // Also check if they are already in our new query object
      var value = req.query[key];
      if (
        Array.isArray(value) ||
        req.WFCatalog.query.hasOwnProperty(databaseKey)
      ) {
        return sendErrorPage(req, res, ERROR.DOUBLE_PARAMETER_GET, key);
      }

      req.WFCatalog.query[databaseKey] = value.toLowerCase();
    }

    next();
  });

  /*
   * Get parser for segment [MWID3.1.A2]
   * ----------------------
   */
  WFCatalog.get(CONFIG.BASE_URL + "query", function (req, res, next) {
    var segment = new Object();

    // Add stream identifiers to the segment list
    var segmentKeys = ["net", "sta", "loc", "cha"];

    for (var i = 0; i < segmentKeys.length; i++) {
      var key = segmentKeys[i];

      if (req.WFCatalog.query.hasOwnProperty(key)) {
        // Check the regex of the input (types.json: stringListWildcard)
        var value = req.WFCatalog.query[key];
        if (!isValidRegex(key, value)) {
          return sendErrorPage(req, res, ERROR.WRONG_TYPE, key);
        }

        // Set the network, station, channel, and location
        // to uppercase and remove them from the query obj
        segment[key] = value.toUpperCase();
        delete req.WFCatalog.query[key];
      }
    }

    // Set the start & end time
    // the sanity is checked later
    segment.ts = req.WFCatalog.query.ts;
    segment.te = req.WFCatalog.query.te;

    delete req.WFCatalog.query.ts;
    delete req.WFCatalog.query.te;

    // Splat to an array to match POST requests
    req.WFCatalog.segments = [segment];

    next();
  });

  /*
   * POST body collector [MWID3.1.B1]
   */
  WFCatalog.post(CONFIG.BASE_URL + "query", function (req, res, next) {
    var body = "";

    // Append data to the buffer
    req.on("data", function (buffer) {
      body += buffer;

      // Throw 400
      if (Buffer.byteLength(body) > CONFIG.MAXIMUM_POST_BYTES) {
        req.WFCatalog.connected = false;
        sendErrorPage(req, res, ERROR.POST_LENGTH_EXCEEDED);
      }
    });

    // Proceed to the next middleware if
    // the user is still connected
    req.on("end", function () {
      // Submitted POST body is empty
      if (Buffer.byteLength(body) === 0) {
        return sendErrorPage(req, res, ERROR.POST_BODY_EMPTY);
      }

      // Only continue if the user is still connected
      // e.g. we may have fried the connection when
      // the POST body was excessively large
      if (req.WFCatalog.connected) {
        req.WFCatalog.POSTbody = body;
        next();
      }
    });
  });

  /*
   * body parser for POST requests [MWID3.1.B2]
   * -----------------------------
   */
  WFCatalog.post(CONFIG.BASE_URL + "query", function (req, res, next) {
    var lines = req.WFCatalog.POSTbody.split("\n").filter(Boolean);

    // Filter the segments from the input
    req.WFCatalog.segments = lines
      .filter(function (x) {
        return x.split(" ").length === 6;
      })
      .map(function (x) {
        return parseSegment(x.split(" "));
      });

    // Sanity check the segments
    if (req.WFCatalog.segments.length === 0) {
      return sendErrorPage(req, res, ERROR.POST_EMPTY_SEGMENTS);
    }

    if (req.WFCatalog.segments.length > CONFIG.MAXIMUM_SEGMENTS) {
      return sendErrorPage(req, res, ERROR.POST_SEGMENTS_EXCEEDED);
    }

    // Get key=value parameters
    var parameters = lines.filter(function (x) {
      return /^\w+=.+$/.test(x);
    });

    if (req.WFCatalog.segments.length + parameters.length !== lines.length) {
      return sendErrorPage(req, res, ERROR.POST_BODY_INVALID);
    }

    // Store everything in the query attribute
    // to match the processing with a GET request
    req.WFCatalog.query = new Object();
    for (var i = 0; i < parameters.length; i++) {
      // Get the key and value
      var keyValues = getKeyAndValue(parameters[i]);
      var databaseKey = keyValues.databaseKey;

      // Client key does not exist as a database key
      // throw 400
      if (!databaseKey) {
        return sendErrorPage(
          req,
          res,
          ERROR.INVALID_PARAMETER_POST,
          keyValues.key,
        );
      }

      // Options specified as key=value may not be a stream identifier
      if (
        databaseKey === "net" ||
        databaseKey === "sta" ||
        databaseKey === "loc" ||
        databaseKey === "cha" ||
        databaseKey === "ts" ||
        databaseKey === "te"
      ) {
        return sendErrorPage(req, res, ERROR.POST_SEGMENT_INVALID, databaseKey);
      }

      // Parameters specified twice will throw an error
      if (req.WFCatalog.query.hasOwnProperty(databaseKey)) {
        return sendErrorPage(
          req,
          res,
          ERROR.DOUBLE_PARAMETER_POST,
          databaseKey,
        );
      }

      req.WFCatalog.query[databaseKey] = keyValues.value;
    }

    next();
  });

  /*
   * function getKeyAndValue
   * > returns client key, database key, and value
   * > from key=value format
   */
  function getKeyAndValue(string) {
    var tmp = string.split("=");

    return {
      databaseKey: getDatabaseKey(tmp[0]),
      key: tmp[0],
      value: tmp[1],
    };
  }

  /*
   * function parseSegment
   * > parses array of segment variables to object literal
   */
  function parseSegment(segment) {
    return {
      te: segment[5],
      ts: segment[4],
      cha: segment[3],
      loc: segment[2],
      sta: segment[1],
      net: segment[0],
    };
  }

  /*
   * function getStringAsBoolean
   * > function to parse 'true' to true and ('false', undefined) to false
   * > otherwise return null
   */
  function getStringAsBoolean(string) {
    if (!string) return false;

    if (string === "true") return true;
    if (string === "false") return false;

    return null;
  }

  /*
   * Middleware to check sanity of start/end times [MWID3.2]
   * ---------------------------------------------
   */
  WFCatalog.all(CONFIG.BASE_URL + "query", function (req, res, next) {
    // Go over all segments and complete a sanity check
    for (var i = 0; i < req.WFCatalog.segments.length; i++) {
      // Start and endtime are required for each segment
      if (req.WFCatalog.segments[i].ts === undefined) {
        return sendErrorPage(req, res, ERROR.START_REQUIRED);
      }
      if (req.WFCatalog.segments[i].te === undefined) {
        return sendErrorPage(req, res, ERROR.END_REQUIRED);
      }

      // Parse the ISO8601 date strings
      var parsedStart = new Date(req.WFCatalog.segments[i].ts);
      if (isNaN(parsedStart)) {
        return sendErrorPage(req, res, ERROR.START_INVALID);
      }
      var parsedEnd = new Date(req.WFCatalog.segments[i].te);
      if (isNaN(parsedEnd)) {
        return sendErrorPage(req, res, ERROR.END_INVALID);
      }

      // Continue sanity check if start beyond end or present day
      if (parsedStart > parsedEnd) {
        return sendErrorPage(req, res, ERROR.START_BEYOND_END);
      }
      if (parsedStart > Date.now()) {
        return sendErrorPage(req, res, ERROR.START_BEYOND_NOW);
      }

      req.WFCatalog.segments[i].ts = parsedStart;
      req.WFCatalog.segments[i].te = parsedEnd;
    }

    next();
  });

  /*
   * Middleware for getting & setting request options [MWID3.3]
   * ------------------------------------------------
   */
  WFCatalog.all(CONFIG.BASE_URL + "query", function (req, res, next) {
    // Set service default options
    // Set some strings to its boolean equivalents
    req.WFCatalog.options = {
      minlen: 0,
      format: "json",
      include: "default",
      gran: "day",
      longestonly: getStringAsBoolean(req.WFCatalog.query.longestonly),
      csegments: getStringAsBoolean(req.WFCatalog.query.csegments),
    };

    // Sanity check the longestonly and csegments
    // null means anything besides 'true', 'false', or undefined was given
    if (req.WFCatalog.options.longestonly === null) {
      return sendErrorPage(req, res, ERROR.WRONG_TYPE, "longestonly");
    }
    delete req.WFCatalog.query.longestonly;

    if (req.WFCatalog.options.csegments === null) {
      return sendErrorPage(req, res, ERROR.WRONG_TYPE, "csegments");
    }
    delete req.WFCatalog.query.csegments;

    // Sanity check for minimumlength, must be a float
    if (req.WFCatalog.query.minlen) {
      if (!isValidRegex("minlen", req.WFCatalog.query.minlen)) {
        return sendErrorPage(req, res, ERROR.WRONG_TYPE, "minlen");
      }
      req.WFCatalog.options.minlen = parseFloat(req.WFCatalog.query.minlen);
      delete req.WFCatalog.query.minlen;
    }

    // Check the include option; 'default', 'sample', 'header', and 'all' are supported
    if (req.WFCatalog.query.include) {
      if (
        !["default", "sample", "header", "all"].inArray(
          req.WFCatalog.query.include,
        )
      ) {
        return sendErrorPage(
          req,
          res,
          ERROR.INCLUDE_UNSUPPORTED,
          req.WFCatalog.query.include,
        );
      }
      req.WFCatalog.options.include = req.WFCatalog.query.include;
      delete req.WFCatalog.query.include;
    }

    // Check the granularity; only 'day' is supported
    if (req.WFCatalog.query.gran) {
      if (req.WFCatalog.query.gran !== "day") {
        return sendErrorPage(
          req,
          res,
          ERROR.GRANULARITY_UNSUPPORTED,
          req.WFCatalog.query.gran,
        );
      }
      req.WFCatalog.options.gran = req.WFCatalog.query.gran;
      delete req.WFCatalog.query.gran;
    }

    // Check the format; only 'json' is supported
    if (req.WFCatalog.query.format) {
      if (req.WFCatalog.query.format !== "json") {
        return sendErrorPage(
          req,
          res,
          ERROR.FORMAT_UNSUPPORTED,
          req.WFCatalog.query.format,
        );
      }
      req.WFCatalog.options.format = req.WFCatalog.query.format;
      delete req.WFCatalog.query.format;
    }

    // If [minimumlength] or [longestonly] is specified
    // include the continuous segments by default
    if (
      req.WFCatalog.options.minlen !== 0 ||
      req.WFCatalog.options.longestonly
    ) {
      req.WFCatalog.options.csegments = true;
    }

    next();
  });

  /*
   * Middleware to parse query with correct types [MWID3.4]
   * ------------------------------------------------
   */
  WFCatalog.all(CONFIG.BASE_URL + "query", function (req, res, next) {
    req.WFCatalog.parsedQuery = new Object();

    // Go over all keys and prepare a parsed MongoDB query
    for (var key in req.WFCatalog.query) {
      var value = req.WFCatalog.query[key];

      // Set the data quality parameter
      // must be either of D, R, Q, M, B
      if (key === "qlt") {
        value = value.toUpperCase();

        if (
          value !== "D" &&
          value !== "R" &&
          value !== "Q" &&
          value !== "M" &&
          value !== "B"
        ) {
          return sendErrorPage(req, res, ERROR.QUALITY_INVALID, value);
        }

        req.WFCatalog.parsedQuery["qlt"] = value;
        continue;
      }

      // Set encoding to uppercase
      if (key === "enc") {
        value = value.toUpperCase();
      }

      // Key value has an extension, must be a metric
      // Get the metric name without an extension for regex matching
      var ext = getMetricExtension(key);
      if (ext) {
        var key = getMetricName(key);
      }

      // Match the pattern of each key & value to the regex database
      if (!isValidRegex(key, value)) {
        return sendErrorPage(req, res, ERROR.WRONG_TYPE, key);
      }

      // Metrics have an extension
      // nest them in the flag group
      // otherwise, simply add (optionally comma delimited)
      // values
      if (ext) {
        value = setType(key, value);
        key = getFlagGroup(key);

        // Create a new nesting if it does not exist
        if (!req.WFCatalog.parsedQuery[key]) {
          req.WFCatalog.parsedQuery[key] = new Object();
        }

        req.WFCatalog.parsedQuery[key][getMongoExtension(ext)] = value;
      } else {
        // Map any comma delimited string
        var list = value.split(",").map(function (x) {
          return setType(key, x);
        });

        req.WFCatalog.parsedQuery[key] =
          list.length > 1
            ? {
                $in: list,
              }
            : list[0];
      }
    }

    next();
  });

  /*
   * Middleware to handle database requests [MWID3.5]
   */
  WFCatalog.all(CONFIG.BASE_URL + "query", function (req, res, next) {
    // Set the HTTP headers for the response
    if (req.WFCatalog.options.format === "json") {
      res.setHeader("Content-Type", "application/json");
      res.setHeader(
        "Content-Disposition",
        "attachment; filename=" + generateFilename(),
      );
    }

    // Get the metrics to be included in the database response
    var included = getIncludedMetrics(req.WFCatalog.options.include);

    if (CONFIG.FILTER.ENABLED) {
      // Make sure to filter by streams but this may be slower
      if (CONFIG.FILTER.STREAMS.length > 0) {
        req.WFCatalog.parsedQuery["fileId"] = {
          $nin: CONFIG.FILTER.STREAMS.map(function (x) {
            return replaceWildcards(x);
          }).filter(function (x) {
            return x !== null;
          }),
        };
      }
    }

    req.WFCatalog.dbRequestStart = new Date();
    req.WFCatalog.nSegments = req.WFCatalog.segments.length;
    req.WFCatalog.nDocuments = 0;
    req.WFCatalog.nBytes = 0;
    req.WFCatalog.nContinuous = 0;

    // Define variables for hoisting
    var documentPointer;
    var cursor, cCursor;
    var asyncReq;

    // Asynchronous implementation of multiple requests through POST
    // For most requests (GET), there is only one database request
    (asyncReq = function () {
      // Impure function to mutate req.WFCatalog.parsedQuery
      // with the query for a new segment
      parseSegmentQuery(req);

      // Open and initialize the cursor to the daily stream collection
      cursor = Mongo.db(CONFIG.MONGO.DBNAME)
        .collection(CONFIG.MONGO.COLLECTION)
        .find(req.WFCatalog.parsedQuery, included);
      cursor.next(processDailyStream);
    })();

    /*
     * Callback to loop over daily stream cursor
     */
    function processDailyStream(err, doc) {
      // Error fetching document or user disconnected; end response
      if (err || !req.WFCatalog.connected) {
        return endResponse(req, res);
      }

      // The cursor exhausted and more segments to be handled
      // Otherwise end the response
      if (doc === null) {
        if (req.WFCatalog.segments.length) {
          return asyncReq();
        }
        return endResponse(req, res);
      }

      req.WFCatalog.nDocuments++;

      // Map the database keys to client keys,
      // and hoist the document so it can be accessed by other functions
      documentPointer = setClientKeys(doc, req.WFCatalog.options.include);

      // If the continuous segments are not requested,
      // or the document is one trace, write the daily metric document
      // and proceed along the cursor
      if (!req.WFCatalog.options.csegments || doc.cont) {
        if (writeStream(req, res, documentPointer)) {
          return cursor.next(processDailyStream);
        }
        return endResponse(req, res);
      }

      // We are required to collect continuous segments
      // for this metric document
      documentPointer.c_segments = new Array();

      // Query for the continuous segments. The stream_id is related
      // to the ._id of a daily metric document
      // Set the minimum length requested by the user
      var cQuery = {
        streamId: ObjectId(doc._id),
        slen: {
          $gte: req.WFCatalog.options.minlen,
        },
      };

      // Longest only requested, limit the cursor to one
      var limit = req.WFCatalog.options.longestonly ? 1 : 0;

      // Open and initialize the continuous cursor
      cCursor = Mongo.db(CONFIG.MONGO.DBNAME)
        .collection(CONFIG.MONGO.C_COLLECTION)
        .find(cQuery)
        .sort({
          slen: 1,
        })
        .limit(limit);
      cCursor.next(processCSegment);
    }

    /*
     * Cursor callback function for the continuous segments
     */
    function processCSegment(err, cDoc) {
      // Error or client disconnected; end response
      if (err || !req.WFCatalog.connected) {
        return endResponse(req, res);
      }

      // Append the continuous segment to the document pointer
      if (cDoc) {
        req.WFCatalog.nContinuous++;
        documentPointer.c_segments.push(setClientKeysContinuous(cDoc));
        return cCursor.next(processCSegment);
      }

      // The cursor has been exhausted; write to stream
      // and proceed with the next daily stream
      if (writeStream(req, res, documentPointer)) {
        return cursor.next(processDailyStream);
      }

      return endResponse(req, res);
    }
  });

  var Mongo;

  // var serverOptions = {
  //   auto_reconnect: CONFIG.MONGO.AUTO_RECONNECT,
  //   poolSize: CONFIG.MONGO.POOL_SIZE,
  //   reconnectTries: 3600 * 24,
  //   reconnectInterval: 1000,
  // };

  async function connect_to_mongo() {
    setMongoAuthentication();
    try {
      Mongo = new MongoClient(CONFIG.MONGO.AUTHHOST, {
        maxPoolSize: CONFIG.MONGO.POOL_SIZE,
      });
      console.log("Connecting to MongoDB Atlas cluster...");
      await Mongo.connect();
      console.log("Successfully connected to MongoDB Atlas!");
    } catch (error) {
      console.error("Connection to MongoDB Atlas failed!", error);
    }
  }

  // Try to connect directly on startup
  connect_to_mongo();

  // Start the WFCatalog on the configured host:port
  WFCatalog.listen(CONFIG.PORT, CONFIG.HOST, function () {
    if (typeof WFCatalogCallback === "function") {
      WFCatalogCallback();
    }
  });

  /* @ function writeStream
   * Handler for writing to the writeable response stream
   * counts the nBytes shipped and properly parses the
   * JSON body
   */
  function writeStream(req, res, data) {
    var json = JSON.stringify(data);
    req.WFCatalog.nBytes += Buffer.byteLength(json);

    // Delimit a document by a comma or open the JSON
    if (req.WFCatalog.nDocuments === 1) {
      res.write("[");
    } else {
      res.write(",");
    }

    res.write(json);

    // Set to 0 for no maximum
    if (CONFIG.MAXIMUM_BYTES_RETURNED === 0) {
      return true;
    }

    return req.WFCatalog.nBytes < CONFIG.MAXIMUM_BYTES_RETURNED;
  }

  /* @ function endReponse
   * Handler at the end the response after all cursors
   * have been exhausted. Fixes the JSON response body
   * and sets the appropriate response code
   */
  function endResponse(req, res) {
    // Time spent querying the database; waiting
    req.WFCatalog.msQueryTime = new Date() - req.WFCatalog.dbRequestStart;

    // User hangup, use nginx code 499 Client Closed Request
    if (!req.WFCatalog.connected) {
      return res.status(499).end();
    }

    // If no documents, return 204
    if (!req.WFCatalog.nDocuments) {
      return res.status(204).end();
    }

    // Close JSON and celebrate a succesful request
    res.write("]");

    return res.status(200).end();
  }

  /*
   * End of WFCatalog query implementation
   */

  /* function generateFilename
   * > generates filename based on the current date and service name
   */
  function generateFilename() {
    return CONFIG.NAME + "-" + new Date().toISOString() + ".json";
  }

  /*
   * function getIncludedMetrics
   * > tells MongoDB what metrics to include in response
   */
  function getIncludedMetrics(include) {
    // Included by default
    var includedParameters = {
      cont: 1,
      created: 1,
      net: 1,
      sta: 1,
      loc: 1,
      cha: 1,
      ts: 1,
      te: 1,
      format: 1,
      nsam: 1,
      ngaps: 1,
      nover: 1,
      srate: 1,
      rlen: 1,
      nrec: 1,
      enc: 1,
      qlt: 1,
      gmax: 1,
      omax: 1,
      avail: 1,
      glen: 1,
      olen: 1,
    };

    // Go over the include options
    // to determine what metrics
    // to include in the result
    if (include === "default") {
      return includedParameters;
    } else if (include === "sample") {
      return includeSamples(includedParameters);
    } else if (include === "header") {
      return includeHeaders(includedParameters);
    } else if (include === "all") {
      return excludeFields();
    }
  }

  /*
   * function excludeFields
   * > get fields to exclude from database response
   * > these fields should not be exposed to the user
   */
  function excludeFields() {
    return {
      files: 0,
      collector: 0,
      status: 0,
      warnings: 0,
      fileId: 0,
    };
  }

  /*
   * function includeHeaders
   * > extend default object literal to
   * > include mSEED headers in response
   */
  function includeHeaders(parameters) {
    parameters["ac_flags"] = 1;
    parameters["dq_flags"] = 1;
    parameters["io_flags"] = 1;
    parameters["tcorr"] = 1;
    parameters["tqmean"] = 1;
    parameters["tqmedian"] = 1;
    parameters["tqlower"] = 1;
    parameters["tqupper"] = 1;
    parameters["tqmin"] = 1;
    parameters["tqmax"] = 1;
    return parameters;
  }

  /*
   * function includeSamples
   * > extend default object literal to
   * > include sample information in response
   */
  function includeSamples(parameters) {
    parameters["smin"] = 1;
    parameters["smax"] = 1;
    parameters["smean"] = 1;
    parameters["smedian"] = 1;
    parameters["stdev"] = 1;
    parameters["rms"] = 1;
    parameters["slower"] = 1;
    parameters["supper"] = 1;
    return parameters;
  }

  /*
   * function setClientKeysContinuous
   * > maps database to clients keys for
   * > continuous segments
   */
  function setClientKeysContinuous(doc) {
    // JSON Schema map for a continuous segment
    return {
      sample_rms: doc["rms"],
      start_time: doc["ts"],
      end_time: doc["te"],
      num_samples: doc["nsam"],
      sample_rate: doc["srate"],
      sample_min: doc["smin"],
      sample_max: doc["smax"],
      sample_mean: doc["smean"],
      sample_lower_quartile: doc["slower"],
      sample_upper_quartile: doc["supper"],
      sample_median: doc["smedian"],
      sample_stdev: doc["stdev"],
      segment_length: doc["slen"],
    };
  }

  /*
   * funcion setClientKeys
   * > maps database keys to keys
   */
  function setClientKeys(doc, includedP) {
    //var created = new Date();
    var schemaDocument = {
      version: CONFIG.WFCATALOG_SCHEMA_VERSION,
      producer: {
        name: CONFIG.ARCHIVE,
        agent: CONFIG.AGENT,
        created: doc["created"],
      },
      station: doc["sta"],
      network: doc["net"],
      location: doc["loc"],
      channel: doc["cha"],
      num_gaps: doc["ngaps"],
      num_overlaps: doc["nover"],
      sum_gaps: doc["glen"],
      sum_overlaps: doc["olen"],
      max_gap: doc["gmax"],
      max_overlap: doc["omax"],
      record_length: doc["rlen"],
      sample_rate: doc["srate"],
      percent_availability: doc["avail"],
      encoding: doc["enc"],
      num_records: doc["nrec"],
      num_samples: doc["nsamp"],
      start_time: doc["ts"],
      end_time: doc["te"],
      format: "miniSEED",
      quality: doc["qlt"],
    };

    // Include the sample metrics to the schema document
    if (includedP === "sample" || includedP === "all") {
      schemaDocument["sample_min"] = doc["smin"];
      schemaDocument["sample_max"] = doc["smax"];
      schemaDocument["sample_mean"] = doc["smean"];
      schemaDocument["sample_median"] = doc["smedian"];
      schemaDocument["sample_stdev"] = doc["stdev"];
      schemaDocument["sample_rms"] = doc["rms"];
      schemaDocument["sample_lower_quartile"] = doc["slower"];
      schemaDocument["sample_upper_quartile"] = doc["supper"];
    }

    // Include the header metrics to the new document
    if (includedP === "header" || includedP === "all") {
      schemaDocument["miniseed_header_percentages"] = {
        timing_quality_mean: doc["tqmean"],
        timing_quality_median: doc["tqmedian"],
        timing_quality_lower_quartile: doc["tqlower"],
        timing_quality_upper_quartile: doc["tqupper"],
        timing_quality_min: doc["tqmin"],
        timing_quality_max: doc["tqmax"],
        timing_correction: doc["tcorr"],
        // When mseed files were processed without the `--flags` argument, it
        // might be that `io`, `dq` and `ac` dictionaries are not avaialble.
        io_and_clock_flags: {
          short_record_read: doc["io_flags"] ? doc["io_flags"]["srr"] : null,
          station_volume: doc["io_flags"] ? doc["io_flags"]["svo"] : null,
          start_time_series: doc["io_flags"] ? doc["io_flags"]["sts"] : null,
          end_time_series: doc["io_flags"] ? doc["io_flags"]["ets"] : null,
          clock_locked: doc["io_flags"] ? doc["io_flags"]["clo"] : null,
          event_in_progress: doc["io_flags"] ? doc["io_flags"]["eip"] : null,
        },
        data_quality_flags: {
          amplifier_saturation: doc["dq_flags"] ? doc["dq_flags"]["asa"] : null,
          digitizer_clipping: doc["dq_flags"] ? doc["dq_flags"]["dic"] : null,
          spikes: doc["dq_flags"] ? doc["dq_flags"]["spi"] : null,
          glitches: doc["dq_flags"] ? doc["dq_flags"]["gli"] : null,
          missing_padded_data: doc["dq_flags"] ? doc["dq_flags"]["mpd"] : null,
          telemetry_sync_error: doc["dq_flags"] ? doc["dq_flags"]["tse"] : null,
          digital_filter_charging: doc["dq_flags"]
            ? doc["dq_flags"]["dfc"]
            : null,
          suspect_time_tag: doc["dq_flags"] ? doc["dq_flags"]["stt"] : null,
        },
        activity_flags: {
          calibration_signal: doc["ac_flags"] ? doc["ac_flags"]["cas"] : null,
          time_correction_applied: doc["ac_flags"]
            ? doc["ac_flags"]["tca"]
            : null,
          event_begin: doc["ac_flags"] ? doc["ac_flags"]["evb"] : null,
          event_end: doc["ac_flags"] ? doc["ac_flags"]["eve"] : null,
          positive_leap: doc["ac_flags"] ? doc["ac_flags"]["pol"] : null,
          negative_leap: doc["ac_flags"] ? doc["ac_flags"]["nel"] : null,
        },
      };
    }

    return schemaDocument;
  }

  /*
   * function getClientKey
   * > map database key to client key
   * > or itself if it does not exist
   */
  function getClientKey(key) {
    return CLIENT_MAP[key] || key;
  }

  /*
   * function parseSegmentQuery
   * > creates the MongoDB query for a single segment
   * > by overwriting properties of the req.WFCatalog.parsedQuery
   * > NET, STA, LOC, CHA, TS, TE
   */
  function parseSegmentQuery(req) {
    var DAILY_MS = 1000 * 60 * 60 * 24;

    // First segment in queue
    var segment = req.WFCatalog.segments.pop();

    // Log each database request
    WFCatalogger.trace(
      {
        id: req.WFCatalog.requestId,
        query: req.WFCatalog.parsedQuery,
        segment: segment,
        options: req.WFCatalog.options,
      },
      "Database Request",
    );

    // Round outwardly to the nearest day
    segment.ts = new Date(DAILY_MS * Math.floor(segment.ts / DAILY_MS));
    segment.te = new Date(DAILY_MS * Math.ceil(segment.te / DAILY_MS));

    // Query documents by the starttime only
    req.WFCatalog.parsedQuery.ts = {
      $gte: segment.ts,
      $lt: segment.te,
    };

    // Go over the network, station, location, and channel
    for (var key in segment) {
      // Start and endtime are already used in the query
      if (key === "ts" || key === "te") continue;

      // The split allows comma delimited inputs, and will be
      // mapped with their wildcards (*, ?) replaced.
      // Also filted any response from replaceWildcards that is null
      var list = segment[key]
        .split(",")
        .map(function (x) {
          return replaceWildcards(x);
        })
        .filter(function (x) {
          return x !== null;
        });

      // Nothing passed the previous null filter
      if (list.length === 0) {
        continue;
      }

      // Format the Mongo query, if multiple parameters use {key: {$in: [values]}},
      // else default to the common {key: value} notation
      req.WFCatalog.parsedQuery[key] =
        list.length > 1
          ? {
              $in: list,
            }
          : list[0];
    }
  }

  /*
   * function replaceWildcards
   * > replaces WFCatalog wildcards with MongoDB wildcards
   */
  function replaceWildcards(input) {
    // No wildcards or oddities
    // simply return the input
    if (!input.match(/[?*-]/)) {
      return input;
    }

    // If there is only a wildcard for a given key,
    // we can ignore it completely
    if (input === "*") {
      return null;
    }

    // Replacement for the location notation
    if (input === "--") {
      return "";
    }

    // Parse RegEx between  ^ EXPRESSION $ with wildcards
    // A "?" will becomes a single character, * multiple
    var input = input.replace(/\?/g, ".").replace(/\*/g, ".*");

    return new RegExp(["^", input, "$"].join(""));
  }

  /*
   * function getFlagGroup
   * > maps flag key to nested group
   * > abbreviations correspond to database keys
   */
  function getFlagGroup(key) {
    switch (key) {
      case "asa":
      case "spi":
      case "gli":
      case "mpd":
      case "tse":
      case "dic":
      case "dfc":
      case "stt":
        return "dq_flags." + key;
      case "evb":
      case "eve":
      case "tca":
      case "pol":
      case "nel":
      case "cas":
      case "eip":
        return "ac_flags." + key;
      case "svo":
      case "lrr":
      case "srr":
      case "sts":
      case "ets":
      case "clo":
        return "io_flags." + key;
      default:
        return key;
    }
  }

  /*
   * function setType
   * > sets the type of floats and integers from string
   */
  function setType(key, value) {
    // Get the expected type for the given key
    var type = TYPES[key];

    // Type of a key is unknown, throw
    if (!type) {
      throw "setType: Unknown type for key " + key;
    }

    // Do the conversion or
    // throw if there is an unknown type
    switch (type) {
      case "float":
      case "floatList":
        return parseFloat(value);
      case "int":
      case "intList":
        return parseInt(value);
      case "string":
      case "stringList":
      case "stringListWildcards":
        return value;
      default:
        throw "setType: Unknown conversion for key " + key;
    }
  }

  /*
   * function isValidRegex
   * > returns true if value for a key matches
   * > the expected regex pattern
   */
  function isValidRegex(key, value) {
    var type = TYPES[key];

    // Throw if there is a problem with an unknown key
    if (!type) {
      throw "isValidRegex: Unknown type for key " + key;
    }

    if (!REGEX_TABLE[type]) {
      throw "isValidRegex: No entry in REGEX_TABLE for key " + key;
    }

    // Test the value against the compiled regex table
    return REGEX_TABLE[type].test(value);
  }

  /*
   * function getMongoExtension
   * > maps WFCatalog extensions to MongoDB extensions
   */
  function getMongoExtension(ext) {
    // Get the proper MongoDB extension from
    // the WFCatalog specification extensions
    switch (ext) {
      case "_eq":
        return "$eq";
      case "_ne":
        return "$ne";
      case "_gt":
        return "$gt";
      case "_ge":
        return "$gte";
      case "_lt":
        return "$lt";
      case "_le":
        return "$lte";
      default:
        throw "getMongoExtension: unknown metric extension requested " + ext;
    }
  }

  /*
   * function getMetricName
   * > returns the name of a metric by slicing off the extension
   */
  function getMetricName(metric) {
    return metric.slice(0, -3);
  }

  /*
   * function getMetricExtension
   * > returns the metric extension (or null)
   */
  function getMetricExtension(metric) {
    if (/_eq$|_ne$|_gt$|_ge$|_lt$|_le$/.test(metric)) {
      return metric.slice(-3);
    }

    return null;
  }

  /*
   * function getDatabasekey
   * > maps client key to database key
   */
  function getDatabaseKey(key) {
    var key = key.toLowerCase();

    // Check if the key has an extension
    // if so, replace the key without the extension
    var ext = getMetricExtension(key);
    if (ext) {
      key = getMetricName(key);
    }

    // Check if every key that has an extension is a metric,
    // if so, map it to a database key and append its extension
    // or _eq by default, if it is not a metric return null
    // If no extension, simply map to the database keys
    if (ext) {
      if (METRICS.inArray(key)) {
        return DB_MAP[key] + (ext || "_eq");
      } else {
        return null;
      }
    }

    return DB_MAP[key] || null;
  }

  /*
   * function sendErrorPage
   * > sends error page to the user
   */
  function sendErrorPage(req, res, error, extra) {
    // Convert the extra variable to the client map for display
    if (extra) {
      extra = getClientKey(extra);
    }

    res.statusCode = error.code;
    res.statusMessage = error.msg.replace("%s", extra);

    var errorStatus =
      "Error " + res.statusCode + ": " + ERROR.STATUS_CODES[error.code];

    // Different message for POST request
    if (req.method === "POST") {
      return res.send(errorStatus + " " + error.msg.replace("%s", extra));
    }

    // For the GET request, show more details
    var response = [
      errorStatus,
      error.msg.replace("%s", extra),
      "Usage details are available from " + CONFIG.DOCUMENTATION_URI,
      "Request:",
      req.url,
      "Request Submitted:",
      req.WFCatalog.requestSubmitted,
      "Service Version:",
      CONFIG.VERSION,
    ].join("\n");

    return res.send(response);
  }

  /*
   * function Array.inArray
   * > returns Boolean whether element is in array
   */
  Array.prototype.inArray = function (element) {
    return this.indexOf(element.toLowerCase()) !== -1;
  };

  /*
   * function getRequestId
   * > generates a random ID to track the request
   */
  function getRequestId() {
    function s4() {
      return Math.floor((1 + Math.random()) * 0x10000)
        .toString(16)
        .substring(1);
    }

    return (
      s4() +
      s4() +
      "-" +
      s4() +
      "-" +
      s4() +
      "-" +
      s4() +
      "-" +
      s4() +
      s4() +
      s4()
    );
  }

  /*
   * function swapMap
   * > translates the DB_MAP to CLIENT_MAP
   * > these maps link database with client keys
   */
  function swapMap(DB_MAP) {
    var swap = new Object();

    for (var key in DB_MAP) {
      swap[DB_MAP[key]] = key;
    }

    return swap;
  }

  /*
   * function setupLogger
   * > sets up the info stream for WFCatalogger to logfile
   */
  function setupLogger() {
    var bunyan = require("bunyan");

    // Default stream is a logfile
    var streams = [
      {
        level: "trace",
        path: CONFIG.LOGPATH + "WFCATALOG-SERVICE.log",
      },
    ];

    // If ES logging is requested add it to the list of streams
    // A working connection is required, authentication is not
    // supported without a license
    if (CONFIG.ELASTICSEARCH.ENABLED) {
      var ES = require("bunyan-elasticsearch");
      var elasticStream = new ES({
        indexPattern: "[" + CONFIG.ELASTICSEARCH.INDEX + "]",
        type: "logs",
        host: CONFIG.ELASTICSEARCH.HOST + ":" + CONFIG.ELASTICSEARCH.PORT,
      });

      elasticStream.on("error", function (err) {
        console.log("Could not save request log to ES.");
      });

      streams.push({
        level: "info",
        stream: elasticStream,
      });
    }

    WFCatalogger = bunyan.createLogger({
      name: "WFCatalog",
      streams: streams,
    });
  }

  /*
   * function compileRegexTable
   * > returns an object literal with
   * > the expected regex patterns
   */
  function compileRegexTable() {
    // Regex types for all values
    // expected by the service
    return {
      float: /^(?:[1-9]\d*|0)?(?:\.\d+)?$/,
      int: /^\d+$/,
      string: /^([0-9a-z_*?]+)$/i,
      stringList: /^([0-9a-z]+,){0,}([0-9a-z]+)$/i,
      stringListWildcards: /^([0-9a-z_*?]+,){0,}([0-9a-z_*?]+)$/i,
      stringLocListWildcards: /^(([0-9a-z_*?]+|--),){0,}([0-9a-z_*?]+|--)$/i,
      floatList: /^(\s*-?\d+(\.\d+)?)(\s*,\s*-?\d+(\.\d+)?)*$/,
      intList: /^(\d+(,\d+)*)?$/,
      query:
        /^\?([\w-?.:*,%]+(=[\w-?.:*,%]*)?(&[\w-?.:*,%]+(=[\w-?.:*,%]*)?)*)?$/,
    };
  }

  /*
   * function setMongoAuthentication
   * > sets host for given user@pass in config
   */
  function setMongoAuthentication() {
    // Set the authenticated host
    if (CONFIG.MONGO.AUTHENTICATE) {
      CONFIG.MONGO.AUTHHOST =
        "mongodb://" +
        CONFIG.MONGO.USER +
        ":" +
        CONFIG.MONGO.PASS +
        "@" +
        CONFIG.MONGO.HOST +
        "/" +
        CONFIG.MONGO.DBNAME;
    } else {
      CONFIG.MONGO.AUTHHOST = "mongodb://" + CONFIG.MONGO.HOST;
    }
  }
};

// The module is called directly; start a single instance
if (require.main === module) {
  var CONFIG = require("./configuration");

  // Start up the WFCatalog
  new module.exports(CONFIG, function () {
    console.log(
      "Single WFCatalog has been started on " + CONFIG.HOST + ":" + CONFIG.PORT,
    );
  });
}
