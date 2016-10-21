/*
 * Test suite for WFCatalog
 * ------------------------
 */

'use strict';

var http = require('http');
var mongoClient = require('mongodb').MongoClient;
var objectId = require('mongodb').ObjectId;
var server = require('./server');

// Load configuration and set database to runtests
var CONFIG = require("./configuration");

// Start the WFCatalog
var WFCatalog = new server(CONFIG, function() {
  startSuite();
});

/*
 * WFCatalog Test Suite
 * --------------------
 */
var suite = function () {

  var METRICS = require('./static/metrics');
  var ERROR = require('./static/errors');

  /*
   * test MongoDB connection
   */
  this.testMongoConnection = function(callback) {
    mongoClient.connect('mongodb://' + CONFIG.MONGO.HOST, function(err, db) {
      return callback(err);
    });
  }

  /*
   * test MongoDB Authenticated connection
   */
  this.testMongoConnectionAuth = function(callback) {
    mongoClient.connect(CONFIG.MONGO.AUTHHOST, function(err, db) {
      return callback(err);
    });
  }

  /*
   * function this.testStartTimeFuture
   * test start time in the future (2133)
   */
  this.testStartTimeFuture = function(callback) {

    var start = '2133-01-01';
    var end = '2133-01-01';

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?start=' + start + '&end=' + end);

    http.request(options, function(response) {

      response.on('data', function(data) {
        
        var err = compareResponse(data, {
          'message': ERROR.START_BEYOND_NOW,
          'request': options.path,
        });

        callback(err)

      });

    }).end();

  }

  /*
   * Pass "string" to a random metric
   * should return errors as metrics must be floats
   */
  this.testRegex = function(callback) {

    var start = '2012-01-01';
    var end = '2012-01-02';

    var random = METRICS[Math.floor(Math.random() * METRICS.length)];
    var options = getOptions('GET', CONFIG.BASE_URL + 'query?start=' + start + '&end=' + end + '&' + random + '=string');

    http.request(options, function(response) {

      response.on('data', function(data) {

        var err = compareResponse(data, {
          'message': {
            'code': ERROR.WRONG_TYPE.code,
            'msg': ERROR.WRONG_TYPE.msg.replace("%s", random)
          },
          'request': options.path,
        });

        callback(err);

      });

    }).end();

  }

  /*
   * Give an invalid end
   */
  this.testInvalidEndTime = function(callback) {

    var start = '2012-01-01';
    var end = '2012-01--01';

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?start=' + start + '&end=' + end);

    http.request(options, function(response) {

      response.on('data', function(data) {
      
        var err = compareResponse(data, {
          'message': ERROR.END_INVALID,
          'request': options.path,
        });

        callback(err);

      });

    }).end();

  }

  /*
   * Give an invalid start
   */
  this.testInvalidStartTime = function(callback) {

    var start = '20121-0s1-01';
    var end = '2012-01-01';

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?start=' + start + '&end=' + end);

    http.request(options, function(response) {

      response.on('data', function(data) {

        var err = compareResponse(data, {
          'message': ERROR.START_INVALID,
          'request': options.path,
        });

        callback(err);

      });

    }).end();

  }

  this.testEndBeforeStartTime = function(callback) {

    var start = '2016-01-01';
    var end = '2015-01-01';

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?start=' + start + '&end=' + end);

    http.request(options, function(response) {

      response.on('data', function(data) {

        var err = compareResponse(data, {
          'message': ERROR.START_BEYOND_END,
          'request': options.path,
        });

        callback(err)

      });

    }).end();

  }

  /*
   * Pass a double parameter in the GET request
   */
  this.testDoubleParameterGET = function(callback) {

    var random = METRICS[Math.floor(Math.random() * METRICS.length)];

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?' + random + '=FIRST&' + random + '=SECOND');

    http.request(options, function(response) {
      
      response.on('data', function(data) {

        // Do a string interpolation on the random parameter
        var err = compareResponse(data, {
          'message': {
            'code': ERROR.DOUBLE_PARAMETER_GET.code,
            'msg': ERROR.DOUBLE_PARAMETER_GET.msg.replace("%s", random)
          },
          'request': options.path,
        });

        callback(err);

      });

    }).end();

  }

  this.testDoubleParameterPOST = function(callback) {

    // Add sample mean to the body twice
    var body = [
      'sample_mean=10',
      'sample_mean=10',
      'NL HGN 02 LOC 2012-01-01 2012-01-02'
    ].join("\n");

    // Set POST options and headers
    var options = getPOSTOptions(body);
    var req = http.request(options, function(response) {

      // POST response is slightly different
      // hardcode the response string
      response.on('data', function(data) {
        var err = data.toString() !== "Error 400: Bad Request " + ERROR.DOUBLE_PARAMETER_POST.msg.replace('%s', 'sample_mean');
        callback(err);
      });
      
    })

    // Write the POST body and end the request
    req.write(body); req.end();

  }

  this.testSegmentAsMetricPOST = function(callback) {

    var body = [
      "net=NL",
      "NL HGN 02 LOC 2012-01-01 2012-01-02"
    ].join("\n");

    // Set options and headers
    var options = getPOSTOptions(body);
    var req = http.request(options, function(response) {

      response.on('data', function(data) {
         var err = data.toString() !== "Error 400: Bad Request " + ERROR.POST_SEGMENT_INVALID.msg.replace('%s', 'net');
         callback(err);
      });

    });

    req.write(body); req.end();

  }


  /*
   * Pass an invalid metric in the POST body
   */
  this.testInvalidMetricPOST = function(callback) {
  
    var body = [
      "not_a_metric=10",
      "NL HGN 02 LOC 2012-01-01 2012-01-02"
    ].join("\n");

    var options = getPOSTOptions(body);
    var req = http.request(options, function(response) {

      response.on('data', function(data) {
        var err = data.toString() !== "Error 400: Bad Request " + ERROR.INVALID_PARAMETER_POST.msg.replace('%s', 'not_a_metric');
        callback(err);
      });

    });

    req.write(body); req.end();

  }

  this.testInvalidPOSTBody = function(callback) {

    var body = [
      "sample_mean=10",
      "THIS IS AN INVALID BODY",
      "NL HGN 02 LOC 2012-01-01 2012-01-02"
    ].join("\n");

    var options = getPOSTOptions(body);
    var req = http.request(options, function(response) {
    
      response.on('data', function(data) {
        var err = data.toString() !== "Error 400: Bad Request " + ERROR.POST_BODY_INVALID.msg;
        callback(err);
      });
 
    });

    req.write(body); req.end();

  }


  this.testNoSegmentsPOST = function(callback) {

    var body = "THIS IS NOT A SEGMENT";
    var options = getPOSTOptions(body);

    var req = http.request(options, function(response) {
      
      response.on('data', function(data) {
        var err = data.toString() !== "Error 400: Bad Request " + ERROR.POST_EMPTY_SEGMENTS.msg;
        callback(err);
      });

    });

    req.write(body); req.end();

  }


  /*
   * Pass an empty POST body
   */
  this.testEmptyPOSTBody = function(callback) {

    var options = getPOSTOptions("");

    var req = http.request(options, function(response) {

      response.on('data', function(data) {
        var err = data.toString() !== "Error 400: Bad Request " + ERROR.POST_BODY_EMPTY.msg;
        callback(err);
      });

    });

    req.write(""); req.end();

  }

  this.testMinlenAsString = function(callback) {

    var start = '2012-01-01';
    var end = '2012-01-01';

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?start=' + start + '&end=' + end + '&minlen=string');

    http.request(options, function(response) {

      response.on('data', function(data) {

        // Do a string interpolation on the random parameter
        var err = compareResponse(data, {
          'message': {
            'code': ERROR.WRONG_TYPE.code,
            'msg': ERROR.WRONG_TYPE.msg.replace("%s", 'minlen')
          },
          'request': options.path,
        });

        callback(err);

      });

    }).end();

  }

  this.testExceedingSegments = function(callback) {

    // Create 11 segments (since joining, we lose one, therefore + 2)
    var body = Array(CONFIG.MAXIMUM_SEGMENTS + 2).join("*NL HGN 02 BHZ 2012-01-01 2012-01-02\n");
    var options = getPOSTOptions(body);

    var req = http.request(options, function(response) {

      response.on('data', function(data) {
        var err = data.toString() !== "Error 413: Payload Too Large " + ERROR.POST_SEGMENTS_EXCEEDED.msg;
        callback(err);
      });

    });

    req.write(body); req.end();

  }

  /*
   * Pass an invalid query string
   */
  this.testInvalidQuery = function(callback) {

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?net=NL&&');

    http.request(options, function(response) {

      response.on('data', function(data) {
        
        var err = compareResponse(data, {
          'message': ERROR.INVALID_QUERY,
          'request': options.path,
        });

        callback(err);

      });

    }).end();

  }

  this.testExceedingPOSTBody = function(callback) {

    var body = Array(CONFIG.MAXIMUM_POST_BYTES + 2).join("*"); 
    var options = getPOSTOptions(body);

    var req = http.request(options, function(response) {

      response.on('data', function(data) {
        var err = data.toString() !== "Error 400: Bad Request " + ERROR.POST_LENGTH_EXCEEDED.msg;
        callback(err);
      });

    });

    req.write(body); req.end();

  }

  this.testEmptyQuery = function(callback) {

    var options = getOptions('GET', CONFIG.BASE_URL + 'query');

    http.request(options, function(response) {

      response.on('data', function(data) {

        var err = compareResponse(data, {
          'message': ERROR.EMPTY_QUERY,
          'request': options.path,
        });

        callback(err);

      });

    }).end();

  }

  /*
   * Query the version
   */
  this.testVersion = function(callback) {

    var options = getOptions('GET', CONFIG.BASE_URL + 'version');

    http.request(options, function(response) {

      response.on('data', function(data) {

        var err = data.toString() !== CONFIG.VERSION;

        callback(err);

      });

    }).end();

  }

  this.testServiceClosed = function(callback) {

    CONFIG.CLOSED = true;

    var options = getOptions('GET', CONFIG.BASE_URL + 'query');

    http.request(options, function(response) {

      response.on('data', function(data) {

        var err = compareResponse(data, {
          'message': ERROR.SERVICE_CLOSED,
          'request': options.path,
        });

        CONFIG.CLOSED = false;
        callback(err);

      });

    }).end();

  }


  this.testWADL = function(callback) {

    // Create MD5 hash
    var EXPECTED_WADL_HASH = "eaa723f996ec3431e84cf845f8dff9ca";

    var hash = require('crypto').createHash('md5')
    var options = getOptions('GET', CONFIG.BASE_URL + 'application.wadl');

    http.request(options, function(response) {

      // Update the hash on data
      response.on('data', function(data) {
        hash.update(data);
      });

      // Digest the hash and compareResponse to what the WADL should be
      response.on('end', function(data) {

        var err = hash.digest('hex') !== EXPECTED_WADL_HASH;

        callback(err);

      });

    }).end();


  }

  /*
   * Test an excessively long query
   */
  this.testExceedingQuery = function(callback) {

    // Add stars to the query up to the maximum + 1 and expect failure
    var query = Array(CONFIG.MAXIMUM_GET_BYTES + 1).join("*");

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?' + query);

    http.request(options, function(response) {

      response.on('data', function(data) {

        var err = compareResponse(data, {
          'message': ERROR.QUERY_LENGTH_EXCEEDED,
          'request': options.path,
        });

        callback(err);

      });

    }).end();

  }


  /*
   * pass all metrics with a random extension
   * look for errors
   */
  this.testAllMetrics = function(callback) {

    var start = '2015-01-01';
    var end = '2017-01-01';

    // Add a random extension
    function _randomExt() {
      var extensions = ["_eq", "_ne", "_lt", "_le", "_gt", "_ge"];
      return extensions[Math.floor(Math.random() * extensions.length)];
    }

    var metrics = METRICS.map(function(metric) {
      return metric + _randomExt();
    });

    // Add fake network so the response is always empty
    // We testing to see if any metrics throw errors
    var options = getOptions('GET', CONFIG.BASE_URL + 'query?net=NONE&start=' + start + '&end=' + end + '&' + metrics.join("=0&") + "=0");

    http.request(options, function(response) {

      // No data returned for 204 response
      // But without this callback it does not work 
      response.on('data', function() {});

      response.on('end', function() {
        response.statusCode !== 204 ? callback('Got statusCode ' + response.statusCode + ' expected 204') : callback(null);
      });

    }).end();

  }

  /*
   * give an unsupported granularity (hour)
   */
  this.testInvalidGranularity = function(callback) {

    var start = '2012-01-01T00:00:00';
    var end = '2012-01-02T00:00:00';

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?start=' + start + '&end=' + end + '&gran=hour');

    http.request(options, function(response) {

      response.on('data', function(data) {

        var err = compareResponse(data, {
          'message': {
            'code': ERROR.GRANULARITY_UNSUPPORTED.code,
            'msg': ERROR.GRANULARITY_UNSUPPORTED.msg.replace('%s', 'hour')
          },
          'request': options.path,
        });

        callback(err)

      });

    }).end();

  }


  /*
   * test unsupported format (xml)
   */
  this.testInvalidFormat = function(callback) {

    var start = '2012-01-01T00:00:00';
    var end = '2012-01-02T00:00:00';

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?start=' + start + '&end=' + end + '&format=xml');

    http.request(options, function(response) {

      response.on('data', function(data) {

        var err = compareResponse(data, {
          'message': {
            'code': ERROR.FORMAT_UNSUPPORTED.code,
            'msg': ERROR.FORMAT_UNSUPPORTED.msg.replace('%s', 'xml')
          },
          'request': options.path,
        });

        callback(err)

      });

    }).end();
  }


  /*
   * test an invalid include parameter (invalid)
   */
  this.testInvalidInclude = function(callback) {

    var start = '2012-01-01T00:00:00';
    var end = '2012-01-02T00:00:00';

    var options = getOptions('GET', CONFIG.BASE_URL + 'query?start=' + start + '&end=' + end + '&include=invalid');

    http.request(options, function(response) {

      response.on('data', function(data) {

        var err = compareResponse(data, {
          'message': {
            'code': ERROR.INCLUDE_UNSUPPORTED.code,
            'msg': ERROR.INCLUDE_UNSUPPORTED.msg.replace('%s', 'invalid')
          },
          'request': options.path,
        });

        callback(err)

      });

    }).end();
  }

}


function compareResponse(a, b) {

  function compare(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
  }

  b.version = CONFIG.VERSION;
  a = parseResponse(a);

  if(!compare(a, b)) {
    return "Response comparison failed.";
  }

  return null;

}


function getPOSTOptions(body) {

  return {
    host: CONFIG.HOST,
    port: CONFIG.PORT,
    method: 'POST',
    path: CONFIG.BASE_URL + 'query',
    headers: {
      'Content-Type': 'text',
      'Content-Length': Buffer.byteLength(body),
      'Connection': false
    }
  }

}

function getOptions(method, path) {

  return {
    host: CONFIG.HOST,
    port: CONFIG.PORT,
    method: method,
    path: path
  }

}

function parseResponse(body) {

  var body = body.toString().split("\n");
  var errorcode = parseInt(body[0].split(" ")[1]);

  return {
    "message": {
      "code": errorcode,
      "msg": body[1]
    },
    "request": body[4],
    "version": body[8],
  }

}

// Main function called after WFCatalog has loaded
function startSuite() {

  process.stdout.write("\n");
 
  var testSuite = new suite;
  var start = Date.now();

  // Get all tests from the suite to an array
  var tests = Object.keys(testSuite).filter(function(x) {
    return typeof(testSuite[x]) === "function";
  }).map(function(x) {
    return {'fn': eval('testSuite.' + x), 'name': x};
  });

  var proceed;
  var nTests = tests.length;
  var nPass = 0;

  // Main loop, called after every test has completed
  (proceed = function() {

    // No more tests, shutdown the suite
    if(!tests.length) shutdown();

    // Get a new test from the array, run it and pass a callback
    // to proceed
    var runningTest = tests.shift();

    var shift = 50 - runningTest.name.length;
    var nTabs = Array(shift).join(" ");
    process.stdout.write('Calling: ' + runningTest.name);

    runningTest.fn(function(err) {

      if(err) {
        process.stdout.write(nTabs + ' \x1b[1m\x1b[31mFAIL [✖] \x1b[0m');
      } else {
        process.stdout.write(nTabs + ' \x1b[1m\x1b[32mPASS [✔] \x1b[0m'); nPass++;
      }

      process.stdout.write('\n'); proceed();

    });
 
  })();

  /*
   * Shutdown function
   */ 
  var shutdown = function() {
    console.log("\nSuccesfully ran " + nPass + "/" + nTests + " tests in " + ((Date.now() - start) * 1e-3).toFixed(3) + " seconds");
    console.log("Gracefully shutting down the WFCatalog");
    process.exit();
  }

}
