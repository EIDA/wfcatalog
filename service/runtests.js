/*
 * Test suite for WFCatalog
 * ------------------------
 */

"use strict";

var fs = require("fs");
var path = require("path");
var http = require("http");
var mongoClient = require("mongodb").MongoClient;
var server = require("./server");

// Load configuration
var CONFIG = require("./configuration");

// A test that has not answered after this time is reported as failed
var TIMEOUT_MS = 10000;

// The documents the collector writes for its bundled archive (three days of
// NL.HGN.02.LHZ). The collector tests keep this file frozen, so the service
// is checked against what the collector really stores.
var FIXTURE_FILE = path.join(
  __dirname,
  "..",
  "collector",
  "tests",
  "expected",
  "mapped_documents.json",
);
var FIXTURE_QUERY = "net=NL&sta=HGN&cha=LHZ&start=2017-01-21&end=2017-01-24";
var FIXTURES = [];

// Start the WFCatalog
var WFCatalog = new server(CONFIG, function () {
  loadFixtures().then(startSuite, function (err) {
    console.error("Could not load the test documents: " + err);
    startSuite();
  });
});

// The service has built its MongoDB connection string from the configured
// database by now. From here on it is pointed at a separate database, so the
// suite inserts and removes its own documents and never touches real data.
if (!CONFIG.MONGO.AUTHHOST) {
  throw new Error("The service did not set CONFIG.MONGO.AUTHHOST on start");
}
var TEST_DBNAME = CONFIG.MONGO.DBNAME + "_runtests";
CONFIG.MONGO.DBNAME = TEST_DBNAME;

/*
 * WFCatalog Test Suite
 * --------------------
 */
var suite = function () {
  var METRICS = require("./static/metrics");
  var ERROR = require("./static/errors");
  var DB_MAP = require("./static/dbmap");

  /*
   * test MongoDB connection
   */
  this.testMongoConnection = function (callback) {
    mongoClient.connect("mongodb://" + CONFIG.MONGO.HOST, function (err, db) {
      return callback(err);
    });
  };

  /*
   * test MongoDB Authenticated connection
   */
  this.testMongoConnectionAuth = function (callback) {
    mongoClient.connect(CONFIG.MONGO.AUTHHOST, function (err, db) {
      return callback(err);
    });
  };

  /*
   * function this.testEmptyLocationGET
   * test should result in an empty response (i.e. HTTP status code 204)
   */
  this.testEmptyLocationGET = function (callback) {
    var options = getOptions(
      "GET",
      CONFIG.BASE_URL +
        "query?net=NET&sta=STA&cha=CHA&LOC=--&" +
        "start=2020-01-01&end=2020-01-02"
    );

    http
      .request(options, function (response) {
        var err =
          response.statusCode === 204
            ? null
            : "Invalid response code: " + response.statusCode;
        callback(err);
      })
      .end();
  };
  /*
   * function this.testStartTimeFuture
   * test start time in the future (2133)
   */
  this.testStartTimeFuture = function (callback) {
    var start = "2133-01-01";
    var end = "2133-01-01";

    var options = getOptions(
      "GET",
      CONFIG.BASE_URL + "query?start=" + start + "&end=" + end
    );

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: ERROR.START_BEYOND_NOW,
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  /*
   * Pass "string" to a random metric
   * should return errors as metrics must be floats
   */
  this.testRegex = function (callback) {
    var start = "2012-01-01";
    var end = "2012-01-02";

    var random = METRICS[Math.floor(Math.random() * METRICS.length)];
    var options = getOptions(
      "GET",
      CONFIG.BASE_URL +
        "query?start=" +
        start +
        "&end=" +
        end +
        "&" +
        random +
        "=string"
    );

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: {
              code: ERROR.WRONG_TYPE.code,
              msg: ERROR.WRONG_TYPE.msg.replace("%s", random),
            },
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  /*
   * Give an invalid end
   */
  this.testInvalidEndTime = function (callback) {
    var start = "2012-01-01";
    var end = "2012-01--01";

    var options = getOptions(
      "GET",
      CONFIG.BASE_URL + "query?start=" + start + "&end=" + end
    );

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: ERROR.END_INVALID,
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  /*
   * Give an invalid start
   */
  this.testInvalidStartTime = function (callback) {
    var start = "20121-0s1-01";
    var end = "2012-01-01";

    var options = getOptions(
      "GET",
      CONFIG.BASE_URL + "query?start=" + start + "&end=" + end
    );

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: ERROR.START_INVALID,
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  this.testEndBeforeStartTime = function (callback) {
    var start = "2016-01-01";
    var end = "2015-01-01";

    var options = getOptions(
      "GET",
      CONFIG.BASE_URL + "query?start=" + start + "&end=" + end
    );

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: ERROR.START_BEYOND_END,
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  /*
   * Pass a double parameter in the GET request
   */
  this.testDoubleParameterGET = function (callback) {
    var random = METRICS[Math.floor(Math.random() * METRICS.length)];

    var options = getOptions(
      "GET",
      CONFIG.BASE_URL + "query?" + random + "=FIRST&" + random + "=SECOND"
    );

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          // Do a string interpolation on the random parameter
          var err = compareResponse(data, {
            message: {
              code: ERROR.DOUBLE_PARAMETER_GET.code,
              msg: ERROR.DOUBLE_PARAMETER_GET.msg.replace("%s", random),
            },
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  this.testDoubleParameterPOST = function (callback) {
    // Add sample mean to the body twice
    var body = [
      "sample_mean=10",
      "sample_mean=10",
      "NL HGN 02 LOC 2012-01-01 2012-01-02",
    ].join("\n");

    // Set POST options and headers
    var options = getPOSTOptions(body);
    var req = http.request(options, function (response) {
      // POST response is slightly different
      // hardcode the response string
      response.on("data", function (data) {
        var err =
          data.toString() !==
          "Error 400: Bad Request " +
            ERROR.DOUBLE_PARAMETER_POST.msg.replace("%s", "sample_mean");
        callback(err);
      });
    });

    // Write the POST body and end the request
    req.write(body);
    req.end();
  };

  this.testSegmentAsMetricPOST = function (callback) {
    var body = ["net=NL", "NL HGN 02 LOC 2012-01-01 2012-01-02"].join("\n");

    // Set options and headers
    var options = getPOSTOptions(body);
    var req = http.request(options, function (response) {
      response.on("data", function (data) {
        var err =
          data.toString() !==
          "Error 400: Bad Request " +
            ERROR.POST_SEGMENT_INVALID.msg.replace("%s", "net");
        callback(err);
      });
    });

    req.write(body);
    req.end();
  };

  /*
   * Pass an invalid metric in the POST body
   */
  this.testInvalidMetricPOST = function (callback) {
    var body = ["not_a_metric=10", "NL HGN 02 LOC 2012-01-01 2012-01-02"].join(
      "\n"
    );

    var options = getPOSTOptions(body);
    var req = http.request(options, function (response) {
      response.on("data", function (data) {
        var err =
          data.toString() !==
          "Error 400: Bad Request " +
            ERROR.INVALID_PARAMETER_POST.msg.replace("%s", "not_a_metric");
        callback(err);
      });
    });

    req.write(body);
    req.end();
  };

  this.testInvalidPOSTBody = function (callback) {
    var body = [
      "sample_mean=10",
      "THIS IS AN INVALID BODY",
      "NL HGN 02 LOC 2012-01-01 2012-01-02",
    ].join("\n");

    var options = getPOSTOptions(body);
    var req = http.request(options, function (response) {
      response.on("data", function (data) {
        var err =
          data.toString() !==
          "Error 400: Bad Request " + ERROR.POST_BODY_INVALID.msg;
        callback(err);
      });
    });

    req.write(body);
    req.end();
  };

  this.testNoSegmentsPOST = function (callback) {
    var body = "THIS IS NOT A SEGMENT";
    var options = getPOSTOptions(body);

    var req = http.request(options, function (response) {
      response.on("data", function (data) {
        var err =
          data.toString() !==
          "Error 400: Bad Request " + ERROR.POST_EMPTY_SEGMENTS.msg;
        callback(err);
      });
    });

    req.write(body);
    req.end();
  };

  /*
   * Pass an empty POST body
   */
  this.testEmptyPOSTBody = function (callback) {
    var options = getPOSTOptions("");

    var req = http.request(options, function (response) {
      response.on("data", function (data) {
        var err =
          data.toString() !==
          "Error 400: Bad Request " + ERROR.POST_BODY_EMPTY.msg;
        callback(err);
      });
    });

    req.write("");
    req.end();
  };

  this.testMinlenAsString = function (callback) {
    var start = "2012-01-01";
    var end = "2012-01-01";

    var options = getOptions(
      "GET",
      CONFIG.BASE_URL +
        "query?start=" +
        start +
        "&end=" +
        end +
        "&minlen=string"
    );

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          // Do a string interpolation on the random parameter
          var err = compareResponse(data, {
            message: {
              code: ERROR.WRONG_TYPE.code,
              msg: ERROR.WRONG_TYPE.msg.replace("%s", "minlen"),
            },
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  this.testExceedingSegments = function (callback) {
    // Create 11 segments (since joining, we lose one, therefore + 2)
    var body = Array(CONFIG.MAXIMUM_SEGMENTS + 2).join(
      "*NL HGN 02 BHZ 2012-01-01 2012-01-02\n"
    );
    var options = getPOSTOptions(body);

    var req = http.request(options, function (response) {
      response.on("data", function (data) {
        var err =
          data.toString() !==
          "Error 413: Payload Too Large " + ERROR.POST_SEGMENTS_EXCEEDED.msg;
        callback(err);
      });
    });

    req.write(body);
    req.end();
  };

  /*
   * Pass an invalid query string
   */
  this.testInvalidQuery = function (callback) {
    var options = getOptions("GET", CONFIG.BASE_URL + "query?net=NL&&");

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: ERROR.INVALID_QUERY,
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  this.testExceedingPOSTBody = function (callback) {
    var body = Array(CONFIG.MAXIMUM_POST_BYTES + 2).join("*");
    var options = getPOSTOptions(body);

    var req = http.request(options, function (response) {
      response.on("data", function (data) {
        var err =
          data.toString() !==
          "Error 400: Bad Request " + ERROR.POST_LENGTH_EXCEEDED.msg;
        callback(err);
      });
    });

    req.write(body);
    req.end();
  };

  this.testEmptyQuery = function (callback) {
    var options = getOptions("GET", CONFIG.BASE_URL + "query");

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: ERROR.EMPTY_QUERY,
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  /*
   * Query the version
   */
  this.testVersion = function (callback) {
    var options = getOptions("GET", CONFIG.BASE_URL + "version");

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = data.toString() !== CONFIG.VERSION;

          callback(err);
        });
      })
      .end();
  };

  this.testServiceClosed = function (callback) {
    CONFIG.CLOSED = true;

    var options = getOptions("GET", CONFIG.BASE_URL + "query");

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: ERROR.SERVICE_CLOSED,
            request: options.path,
          });

          CONFIG.CLOSED = false;
          callback(err);
        });
      })
      .end();
  };

  this.testWADL = function (callback) {
    // The service must return application.wadl as it is on disk
    var crypto = require("crypto");
    var EXPECTED_WADL_HASH = crypto
      .createHash("md5")
      .update(fs.readFileSync(path.join(__dirname, "application.wadl")))
      .digest("hex");

    var hash = crypto.createHash("md5");
    var options = getOptions("GET", CONFIG.BASE_URL + "application.wadl");

    http
      .request(options, function (response) {
        // Update the hash on data
        response.on("data", function (data) {
          hash.update(data);
        });

        // Digest the hash and compareResponse to what the WADL should be
        response.on("end", function (data) {
          var err = hash.digest("hex") !== EXPECTED_WADL_HASH;

          callback(err);
        });
      })
      .end();
  };

  /*
   * Test an excessively long query
   */
  this.testExceedingQuery = function (callback) {
    // Add stars to the query up to the maximum + 1 and expect failure
    var query = Array(CONFIG.MAXIMUM_GET_BYTES + 1).join("*");

    var options = getOptions("GET", CONFIG.BASE_URL + "query?" + query);

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: ERROR.QUERY_LENGTH_EXCEEDED,
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  /*
   * pass all metrics with a random extension
   * look for errors
   */
  this.testAllMetrics = function (callback) {
    var start = "2015-01-01";
    var end = "2017-01-01";

    // Add a random extension
    function _randomExt() {
      var extensions = ["_eq", "_ne", "_lt", "_le", "_gt", "_ge"];
      return extensions[Math.floor(Math.random() * extensions.length)];
    }

    var metrics = METRICS.map(function (metric) {
      return metric + _randomExt();
    });

    // Add fake network so the response is always empty
    // We testing to see if any metrics throw errors
    var options = getOptions(
      "GET",
      CONFIG.BASE_URL +
        "query?net=NONE&start=" +
        start +
        "&end=" +
        end +
        "&" +
        metrics.join("=0&") +
        "=0"
    );

    http
      .request(options, function (response) {
        // No data returned for 204 response
        // But without this callback it does not work
        response.on("data", function () {});

        response.on("end", function () {
          response.statusCode !== 204
            ? callback(
                "Got statusCode " + response.statusCode + " expected 204"
              )
            : callback(null);
        });
      })
      .end();
  };

  /*
   * give an unsupported granularity (hour)
   */
  this.testInvalidGranularity = function (callback) {
    var start = "2012-01-01T00:00:00";
    var end = "2012-01-02T00:00:00";

    var options = getOptions(
      "GET",
      CONFIG.BASE_URL + "query?start=" + start + "&end=" + end + "&gran=hour"
    );

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: {
              code: ERROR.GRANULARITY_UNSUPPORTED.code,
              msg: ERROR.GRANULARITY_UNSUPPORTED.msg.replace("%s", "hour"),
            },
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  /*
   * test unsupported format (xml)
   */
  this.testInvalidFormat = function (callback) {
    var start = "2012-01-01T00:00:00";
    var end = "2012-01-02T00:00:00";

    var options = getOptions(
      "GET",
      CONFIG.BASE_URL + "query?start=" + start + "&end=" + end + "&format=xml"
    );

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: {
              code: ERROR.FORMAT_UNSUPPORTED.code,
              msg: ERROR.FORMAT_UNSUPPORTED.msg.replace("%s", "xml"),
            },
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };

  /*
   * test an invalid include parameter (invalid)
   */
  this.testInvalidInclude = function (callback) {
    var start = "2012-01-01T00:00:00";
    var end = "2012-01-02T00:00:00";

    var options = getOptions(
      "GET",
      CONFIG.BASE_URL +
        "query?start=" +
        start +
        "&end=" +
        end +
        "&include=invalid"
    );

    http
      .request(options, function (response) {
        response.on("data", function (data) {
          var err = compareResponse(data, {
            message: {
              code: ERROR.INCLUDE_UNSUPPORTED.code,
              msg: ERROR.INCLUDE_UNSUPPORTED.msg.replace("%s", "invalid"),
            },
            request: options.path,
          });

          callback(err);
        });
      })
      .end();
  };
  
  /*
   * Tests an response too large to return as configured by MAXIMUM_BYTES_RETURNED > 0
   */
  this.testPayloadTooLarge = function (callback) {
    var options = getOptions(
      "GET",
      CONFIG.BASE_URL +
        "query?network=NL&station=HGN&include=sample&start=2017-01-21&end=2017-01-24",
    );

    // Less than one document, so the limit is always exceeded
    var prevMaxBytes = CONFIG.MAXIMUM_BYTES_RETURNED;
    CONFIG.MAXIMUM_BYTES_RETURNED = 100;

    request(options, null, function (status, text) {
      CONFIG.MAXIMUM_BYTES_RETURNED = prevMaxBytes;

      if (!text) {
        return callback("Got statusCode " + status + " and an empty body");
      }

      callback(
        compareResponse(text, {
          message: {
            code: ERROR.MAXIMUM_PAYLOAD_EXCEEDED.code,
            msg: ERROR.MAXIMUM_PAYLOAD_EXCEEDED.msg,
          },
          request: options.path,
        }),
      );
    });
  };

  /*
   * Every metric the collector stores at the top level of a daily document
   * must be returned under its client name with the same value.
   * (#16: num_samples was read from a database key that does not exist)
   */
  this.testDailyMetricsFromCollector = function (callback) {
    var names = METRICS.concat([
      "quality",
      "sample_rate",
      "record_length",
      "encoding",
      "num_records",
    ]);

    queryFixtures("include=all", function (err, documents) {
      if (err) {
        return callback(err);
      }

      var problems = [];

      documents.forEach(function (doc) {
        var stored = findFixture(doc);
        var header = doc.miniseed_header_percentages || {};

        names.forEach(function (name) {
          var expected = stored[DB_MAP[name]];

          // Header flags are stored in sub documents, see the next test
          if (expected === undefined) {
            return;
          }

          var actual = doc[name] !== undefined ? doc[name] : header[name];
          if (JSON.stringify(actual) !== JSON.stringify(expected)) {
            problems.push(
              name +
                ": stored " +
                JSON.stringify(expected) +
                ", returned " +
                JSON.stringify(actual),
            );
          }
        });
      });

      callback(problems.length ? problems.join("; ") : null);
    });
  };

  /*
   * Every header flag the collector stores must be returned in the matching
   * group with the same value, and nothing else may appear in that group.
   * (#16: long_record_read was missing, event_in_progress was read from the
   * io flags while the collector stores it with the activity flags)
   */
  this.testHeaderFlagsFromCollector = function (callback) {
    var GROUPS = {
      io_flags: "io_and_clock_flags",
      dq_flags: "data_quality_flags",
      ac_flags: "activity_flags",
    };

    queryFixtures("include=all", function (err, documents) {
      if (err) {
        return callback(err);
      }

      var problems = [];

      documents.forEach(function (doc) {
        var stored = findFixture(doc);
        var header = doc.miniseed_header_percentages || {};

        Object.keys(GROUPS).forEach(function (group) {
          var returned = header[GROUPS[group]] || {};

          METRICS.forEach(function (name) {
            var expected = stored[group][DB_MAP[name]];

            if (expected === undefined) {
              if (returned[name] !== undefined) {
                problems.push(
                  GROUPS[group] + "." + name + " is not stored in " + group,
                );
              }
            } else if (returned[name] !== expected) {
              problems.push(
                GROUPS[group] +
                  "." +
                  name +
                  ": stored " +
                  expected +
                  ", returned " +
                  returned[name],
              );
            }
          });
        });
      });

      callback(problems.length ? problems.join("; ") : null);
    });
  };

  /*
   * The continuous segments of a day with gaps must be returned with it
   */
  this.testContinuousSegmentsFromCollector = function (callback) {
    queryFixtures("csegments=true", function (err, documents) {
      if (err) {
        return callback(err);
      }

      var problems = [];
      var nSegments = 0;

      documents.forEach(function (doc) {
        var stored = findFixture(doc);

        // The collector stores no segments for a continuous day
        if (stored.cont) {
          return;
        }

        var returned = doc.c_segments || [];
        if (returned.length !== stored.segments.length) {
          return problems.push(
            doc.start_time +
              ": stored " +
              stored.segments.length +
              " segments, returned " +
              returned.length,
          );
        }

        returned.forEach(function (segment, i) {
          nSegments++;
          if (segment.num_samples !== stored.segments[i].nsam) {
            problems.push(
              doc.start_time +
                ": segment num_samples stored " +
                stored.segments[i].nsam +
                ", returned " +
                segment.num_samples,
            );
          }
        });
      });

      if (!nSegments && !problems.length) {
        problems.push("The test documents have no continuous segments");
      }

      callback(problems.length ? problems.join("; ") : null);
    });
  };

  /*
   * A float written with a decimal point must be accepted in a POST body
   * (#10: max_gap_gt=5.0 was answered with 400)
   */
  this.testFloatValuePOST = function (callback) {
    var body = "max_gap_gt=5.0\nNL HGN * * 2017-01-21 2017-01-24\n";
    var expected = FIXTURES.filter(function (doc) {
      return doc.gmax > 5.0;
    }).length;

    if (!expected) {
      return callback("The test documents have no gap longer than 5 seconds");
    }

    request(getPOSTOptions(body), body, function (status, text) {
      if (status !== 200) {
        return callback("Got statusCode " + status + " expected 200");
      }

      var nDocuments = JSON.parse(text).length;
      callback(
        nDocuments === expected
          ? null
          : "Got " + nDocuments + " documents expected " + expected,
      );
    });
  };

  /*
   * configuration.json.sample must be valid JSON with the options the
   * service cannot start without
   */
  this.testConfigurationSample = function (callback) {
    var sample;

    try {
      sample = JSON.parse(
        fs.readFileSync(path.join(__dirname, "configuration.json.sample")),
      );
    } catch (e) {
      return callback("configuration.json.sample: " + e.message);
    }

    var missing = ["HOST", "PORT", "BASE_URL", "MONGO"].filter(function (key) {
      return sample[key] === undefined;
    });

    callback(missing.length ? "Missing options: " + missing.join(", ") : null);
  };

  /*
   * Every "type" in wf_metadata_schema.json must be a JSON Schema type name
   * (#16: three properties had an object with an enum as their type)
   */
  this.testSchemaTypes = function (callback) {
    var TYPES = [
      "array",
      "boolean",
      "integer",
      "null",
      "number",
      "object",
      "string",
    ];
    var problems = [];
    var schema;

    try {
      schema = JSON.parse(
        fs.readFileSync(path.join(__dirname, "..", "wf_metadata_schema.json")),
      );
    } catch (e) {
      return callback("wf_metadata_schema.json: " + e.message);
    }

    (function walk(node, where) {
      if (node === null || typeof node !== "object") {
        return;
      }

      if (node.type !== undefined) {
        var valid = [].concat(node.type).every(function (type) {
          return TYPES.indexOf(type) !== -1;
        });
        if (!valid) {
          problems.push(where + ": type is " + JSON.stringify(node.type));
        }
      }

      // Keywords that hold named sub schemas
      ["properties", "patternProperties", "definitions"].forEach(
        function (keyword) {
          Object.keys(node[keyword] || {}).forEach(function (name) {
            walk(node[keyword][name], where + "/" + name);
          });
        },
      );

      // Keywords that hold one sub schema or a list of them
      ["items", "additionalProperties", "not", "allOf", "anyOf", "oneOf"].forEach(
        function (keyword) {
          [].concat(node[keyword] || []).forEach(function (child) {
            walk(child, where + "/" + keyword);
          });
        },
      );
    })(schema, "#");

    callback(problems.length ? problems.join("; ") : null);
  };

  /*
   * Every field the schema requires must be in a returned document
   * (the schema required waveform_format, the service returns format)
   */
  this.testSchemaRequiredFields = function (callback) {
    var schema;

    try {
      schema = JSON.parse(
        fs.readFileSync(path.join(__dirname, "..", "wf_metadata_schema.json")),
      );
    } catch (e) {
      return callback("wf_metadata_schema.json: " + e.message);
    }

    queryFixtures("include=all&csegments=true", function (err, documents) {
      if (err) {
        return callback(err);
      }

      var problems = {};

      (function check(node, value, where) {
        if (node === null || typeof node !== "object") {
          return;
        }

        // A reference to a definition in the same file
        if (typeof node.$ref === "string") {
          check(schema.definitions[node.$ref.split("/").pop()], value, where);
        }

        if (Array.isArray(value)) {
          return value.forEach(function (element) {
            check(node.items, element, where);
          });
        }

        if (value === null || typeof value !== "object") {
          return;
        }

        (node.required || []).forEach(function (name) {
          if (value[name] === undefined) {
            problems[where + name] = true;
          }
        });

        Object.keys(node.properties || {}).forEach(function (name) {
          if (value[name] !== undefined) {
            check(node.properties[name], value[name], where + name + ".");
          }
        });
      })({ items: schema }, documents, "");

      var missing = Object.keys(problems);
      callback(
        missing.length
          ? "Required by the schema, not returned: " + missing.join(", ")
          : null,
      );
    });
  };
};

/*
 * Insert the collector documents into the test database
 */
async function loadFixtures() {
  var documents = JSON.parse(fs.readFileSync(FIXTURE_FILE));
  var client = await mongoClient.connect(CONFIG.MONGO.AUTHHOST, {
    serverSelectionTimeoutMS: TIMEOUT_MS,
  });

  // The file holds dates as "2017-01-21 00:00:00" in UTC
  function asDate(text) {
    return new Date(text.replace(" ", "T") + "Z");
  }

  try {
    var db = client.db(TEST_DBNAME);
    await db.dropDatabase();

    for (var i = 0; i < documents.length; i++) {
      var daily = Object.assign({}, documents[i].daily, {
        ts: asDate(documents[i].daily.ts),
        te: asDate(documents[i].daily.te),
        created: new Date(),
      });
      var inserted = await db
        .collection(CONFIG.MONGO.COLLECTION)
        .insertOne(daily);

      // Segments point to their daily document, as the collector stores them
      var segments = documents[i].c_segments.map(function (segment) {
        return Object.assign({}, segment, {
          streamId: inserted.insertedId,
          ts: asDate(segment.ts),
          te: asDate(segment.te),
        });
      });
      if (segments.length) {
        await db.collection(CONFIG.MONGO.C_COLLECTION).insertMany(segments);
      }

      daily.segments = segments;
      FIXTURES.push(daily);
    }
  } finally {
    await client.close();
  }
}

/*
 * Remove the test database
 */
async function removeFixtures() {
  var client = await mongoClient.connect(CONFIG.MONGO.AUTHHOST, {
    serverSelectionTimeoutMS: TIMEOUT_MS,
  });

  try {
    await client.db(TEST_DBNAME).dropDatabase();
  } finally {
    await client.close();
  }
}

/*
 * Send a request and pass the status code and the complete body on
 */
function request(options, body, callback) {
  var req = http.request(options, function (response) {
    var chunks = [];

    response.on("data", function (chunk) {
      chunks.push(chunk);
    });

    response.on("end", function () {
      callback(response.statusCode, Buffer.concat(chunks).toString());
    });
  });

  if (body) {
    req.write(body);
  }
  req.end();
}

/*
 * Query the test documents and pass on one returned document for each
 */
function queryFixtures(parameters, callback) {
  if (!FIXTURES.length) {
    return callback("The test documents were not loaded");
  }

  var options = getOptions(
    "GET",
    CONFIG.BASE_URL + "query?" + FIXTURE_QUERY + "&" + parameters,
  );

  request(options, null, function (status, text) {
    if (status !== 200) {
      return callback("Got statusCode " + status + " expected 200");
    }

    var documents = JSON.parse(text);
    if (documents.length !== FIXTURES.length) {
      return callback(
        "Got " + documents.length + " documents expected " + FIXTURES.length,
      );
    }

    var unknown = documents.filter(function (doc) {
      return !findFixture(doc);
    });
    if (unknown.length) {
      return callback("Got a document that is not a test document");
    }

    callback(null, documents);
  });
}

/*
 * The stored test document for a returned document
 */
function findFixture(doc) {
  return FIXTURES.filter(function (stored) {
    return stored.ts.toISOString() === doc.start_time;
  })[0];
}

function compareResponse(a, b) {
  function compare(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
  }

  b.version = CONFIG.VERSION;
  a = parseResponse(a);

  if (!compare(a, b)) {
    return "Response comparison failed.";
  }

  return null;
}

function getPOSTOptions(body) {
  return {
    host: CONFIG.HOST,
    port: CONFIG.PORT,
    method: "POST",
    path: CONFIG.BASE_URL + "query",
    headers: {
      "Content-Type": "text",
      "Content-Length": Buffer.byteLength(body),
      Connection: false,
    },
  };
}

function getOptions(method, path) {
  return {
    host: CONFIG.HOST,
    port: CONFIG.PORT,
    method: method,
    path: path,
  };
}

function parseResponse(body) {
  var body = body.toString().split("\n");
  var errorcode = parseInt(body[0].split(" ")[1]);

  return {
    message: {
      code: errorcode,
      msg: body[1],
    },
    request: body[4],
    version: body[8],
  };
}

// Main function called after WFCatalog has loaded
function startSuite() {
  process.stdout.write("\n");

  var testSuite = new suite();
  var start = Date.now();

  // Get all tests from the suite to an array
  var tests = Object.keys(testSuite)
    .filter(function (x) {
      return typeof testSuite[x] === "function";
    })
    .map(function (x) {
      return { fn: eval("testSuite." + x), name: x };
    });

  var proceed;
  var nTests = tests.length;
  var nPass = 0;

  // Main loop, called after every test has completed
  (proceed = function () {
    // No more tests, shutdown the suite
    if (!tests.length) return shutdown();

    // Get a new test from the array, run it and pass a callback
    // to proceed
    var runningTest = tests.shift();

    var shift = 50 - runningTest.name.length;
    var nTabs = Array(shift).join(" ");
    process.stdout.write("Calling: " + runningTest.name);

    // A test reports once; later calls and calls after the timeout are ignored
    var reported = false;
    var report = function (err) {
      if (reported) return;
      reported = true;
      clearTimeout(timer);

      if (err) {
        process.stdout.write(nTabs + " \x1b[1m\x1b[31mFAIL [✖] \x1b[0m");
      } else {
        process.stdout.write(nTabs + " \x1b[1m\x1b[32mPASS [✔] \x1b[0m");
        nPass++;
      }

      process.stdout.write("\n");
      if (typeof err === "string") {
        process.stdout.write("  " + err + "\n");
      }
      proceed();
    };

    var timer = setTimeout(function () {
      report("No answer within " + TIMEOUT_MS / 1000 + " seconds");
    }, TIMEOUT_MS);

    try {
      runningTest.fn(report);
    } catch (e) {
      report(String(e));
    }
  })();

  /*
   * Shutdown function
   */
  function shutdown() {
    console.log(
      "\nSuccesfully ran " +
        nPass +
        "/" +
        nTests +
        " tests in " +
        ((Date.now() - start) * 1e-3).toFixed(3) +
        " seconds"
    );
    console.log("Gracefully shutting down the WFCatalog");

    // Exit with an error code if a test failed, so callers can rely on it
    var exit = function () {
      process.exit(nPass === nTests ? 0 : 1);
    };
    removeFixtures().then(exit, exit);
  }
}
