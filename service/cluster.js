var cluster = require('cluster');

var WFCatalog = require('./server');
var CONFIG = require('./configuration');

var numWorkers = require('os').cpus().length;

// Start the cluster
if(cluster.isMaster) {

  for(var i = 0; i < Math.min(numWorkers, CONFIG['MAXIMUM_CORES']); i++) {
    cluster.fork();
  }

  // If one of the workers dies, restart
  cluster.on('exit', function(worker, code, signal) {
    if(CONFIG.RESPAWN) {
      console.log('[Worker ' + worker.process.pid + '] killed with code: ' + code + ', and signal: ' + signal + '. Respawning.');
      cluster.fork();
    }
  });

} else {

  // Create the WFCatalogs
  // Wrap in closure to pass worker.id
  (function(id) {
    CONFIG.WORKER = id;
    new WFCatalog(CONFIG, function() {
      console.log("[Worker " + id + "] WFCatalog has been started on " + CONFIG.HOST + ":" + CONFIG.PORT);
    });
  })(cluster.worker.id);

}

