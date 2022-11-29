var http = require("http");
var httpProxy = require("http-proxy");
var proxy = httpProxy.createProxyServer({});

// List of test servers
var servers = ["http://127.0.0.1:3001", "http://127.0.0.1:3002"];

// Select the type  of balancing
// supported: "roundRobin" or "random"
var type = "roundRobin";

/*
 * Naive load balancer
 * Draw a random server and connect to it
 */
var server = http.createServer(function (req, res) {
  // Either random or round robin
  if (type === "random") {
    var target = randomServer();
  } else if (type === "roundRobin") {
    var target = roundRobin();
  }

  proxy.web(req, res, { target: target }, function (err) {
    if (err) {
      console.log(err);
    }
  });
});

// Return a random server
var randomServer = function () {
  return servers[Math.floor(Math.random() * servers.length) + 0];
};

// Return next in line
var counter = 0;
var roundRobin = function () {
  var server = servers[counter];
  counter = (counter + 1) % servers.length;
  return server;
};

console.log("The load-balancer is running on port 3000");
server.listen(3000, "127.0.0.1");
