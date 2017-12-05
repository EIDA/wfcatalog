var cache, channelCodes;
var WFCATALOG_ADDRESS = "https://www.orfeus-eu.org/eidaws/wfcatalog/1/query";
var SUGGESTION_SCRIPT = "./scripts/filter-by.php";
var ENABLE_SUGGESTIONS = false;
var NODE = "ORFEUS Data Center"

$(function () {

  // Suggestions are read from the EIDA db
  // and show available networks, stations from a particular node
  // this is optional
  if(ENABLE_SUGGESTIONS) {

    // Station typeahead
    $("#station").typeahead({
      "minlength": 0,
      "items": 10,
      "source": function(_, process) {
        var network = $("#network").val();
        if(network === "") {
          return new Array();
        }
        return $.get(SUGGESTION_SCRIPT, {"network": network}, function(json, _, jqXHR) {
          if(jqXHR.status === 200) {
            process(json.sort());
          }
        });
      }
    });
  
    // Network typeahead
    $("#network").typeahead({
      "minlength": 0,
      "items": 10,
      "source": function(_, process) {
        return $.get(SUGGESTION_SCRIPT, null, function(json, _, jqXHR) {
          if(jqXHR.status === 200) {
            process(json.sort());
          }
        });
      }
    });

  }

  function controlsVisible(b) {
    b ? $("#controls").show() : $("#controls").hide();
  }

  function progressVisible(b) {
    b ? $("#progress").show() : $("#progress").hide();
  }

  // Submit the Ajax request
  $("#request").click(function () {

    progressVisible(true);
    controlsVisible(false);

    // Get the user input
    var net = $("#network").val();
    var sta = $("#station").val();
    var start = $("#dateMin").val();
    var end = $("#dateMax").val();

    if(net === "" || sta === "" || start === "" || end === "") {
      $("#infoContainer").html("Fill in all request parameters.");
      $("#infoContainer").show();
      return progressVisible(false);
    }

    var queryString = "?" + [
      "network=" + net,
      "station=" + sta,
      "start=" + start,
      "end=" + end,
      "include=sample",
    ].join("&");

    $.ajax({
      "dataType": "JSON",
      "url": WFCATALOG_ADDRESS + queryString,
      "type": "GET",
      "error": function(error) {
        $("#infoContainer").html("The WFCatalog returned an error.");
        $("#infoContainer").show();
      },
      "success": function(response, m, xhr) {
    
        progressVisible(false);

        if(xhr.status === 204) {
          $("#infoContainer").html("No metrics were found for this request.");
          $("#infoContainer").show();
          return;
        }

        $("#infoContainer").hide();

        dataCache = new Object();

        // Collect the channels in cache
        var docChan;
        for(var i = 0; i < response.length; i++) {
          docChan = response[i].location ? response[i].location + "." + response[i].channel : response[i].channel;
          if(!dataCache.hasOwnProperty(docChan)) {
            dataCache[docChan] = new Array();
          }
          dataCache[docChan].push(response[i]);
        }

        // Empty the channel selector
        $("#channelCodes").empty();

        // Collect all channels
        channelCodes = new Object();
        var channelIndexes = new Array();

        for(var key in dataCache) {
          var channelIndex = key.substring(0, key.length - 1);
          if(!channelCodes.hasOwnProperty(channelIndex)) {
            channelCodes[channelIndex] = new Array();;
            channelIndexes.push(channelIndex);
          }
          channelCodes[channelIndex].push(key);
        }

        channelIndexes.sort();

        for(var i = 0; i < channelIndexes.length; i++) {
          addOption(channelIndexes[i]);
        }

        // Sort the components alphabetically
        for(var key in channelCodes) {
          channelCodes[key].sort();
        }

        controlsVisible(true);

        cache = {
          "data": dataCache,
          "days": daysBetween(start, end)
        }

        plotCache();

      }

    });

  });

  // When a trigger is changed, re-plot the cache
  $(".trigger").change(function() {
    plotCache();
  });

});

/*
 * function generateData
 *
 * Gets the specific metric from the data array and
 * adds datetime to make time series
 *
 */
function generateData(data, parameter) {

  var filter = $("#filter").is(":checked");

  var plotData = data.map(function(x) {
    return {"x": Date.parse(x.start_time), "y": x[parameter]}
  });

  if(filter) {

   var length;

   while(true) {

     length = plotData.length;
     plotData = filterData(plotData);

     if(length === plotData.length) {
       break;
     }

   } 

  }

  return plotData;

}

/*
 * Function filterData
 *
 * returns data from array within 4 sigma of average
 *
 */
function filterData(data) {

  var average, sigma, absAverage;

  var sum = 0;
  var sumSquared = 0;

  for(var i = 0; i < data.length; i++) {
    sum += data[i].y;
  }

  average = sum / data.length;

  for(var i = 0; i < data.length; i++) {
    sumSquared += Math.pow((data[i].y  - average), 2);
  }

  sigma = 4 * Math.sqrt(sumSquared / data.length);

  absAverage = Math.abs(average);

  return data.filter(function(x) {
    return (absAverage - sigma) < Math.abs(x.y) && Math.abs(x.y) < (absAverage + sigma)
  });

}

/*
 * Function daysBetween
 *
 * returns the number of days between two dates
 * 
 */
function daysBetween(start, end) {

  var SECONDS_ONE_DAY = 24 * 60 * 60 * 1000;

  var firstDate = Date.parse(start);
  var secondDate = Date.parse(end);

  return Math.round(Math.abs((firstDate - secondDate) / (SECONDS_ONE_DAY)));

}

/*
 * Function plotCache
 *
 * Plots data cache to metric graphs
 *
 */
function plotCache() {

  // Clear the chart container
  $("#chartContainer").html("");

  var selectedChannel = $("#channelCodes").val();
  var selectedParameter = $('#parameters').val();
  var startDate = $("#dateMin").val();
  var endDate = $("#dateMax").val();
  var network = $("#network").val();
  var station = $("#station").val();

  var stream = {
    "net": network,
    "sta": station,
    "loc": selectedChannel.split(".")[0] || null
  }

  // Generate info tooltip
  var text = [
    "Charts showing the",
    "<b>" + $('#parameters option:selected').text() + "</b>",
    "for all components of channel",
    "<b>" + selectedChannel + "?</b>",
    "for",
    "<b>" + cache.days + "</b>",
    "days between",
    "<b>" + startDate + "</b> and <b>" + endDate + "</b>."
  ].join(" ");

  $("#chartInformation").html(text);

  // Go over all components in the channel
  for(var i = 0; i < channelCodes[selectedChannel].length; i++) {

    var component = channelCodes[selectedChannel][i];

    var title = [network, station, component].join(".");
    var data = generateData(cache.data[component], selectedParameter);

    stream.cha = component;

    createChart(component, data, title, stream);

  }

}

function createChart(id, data, title, stream) {

  var id = id.replace(".", "-");

  $("#chartContainer").append("<p><div id='container-" + id + "'style='height: 400px; max-width: 800px; margin: 0 auto'></div>");

  // Create a chart
  $("#container-" + id).highcharts({
    'chart': {
      'zoomType': 'xy',
      'type': 'scatter'
    },
    'title': {
      'style': {
        'color': '#C03'
      },
      'text': title
    },
    'subtitle': {
      'text': 'Displaying metric data for <b>' + data.length + '</b> out of <b>' + cache.days + '</b> days'
    },         
    'xAxis': {
      'min': new Date($('#dateMin').val()).getTime(),
      'max': new Date($('#dateMax').val()).getTime(),
      'type': 'datetime',
      'title': {
        'enabled': true,
        'text': 'Date'
      },
    },
    'yAxis': {
      'title': {
        'text': $('#parameters option:selected').text()
      }
    },
    'tooltip': {
      'formatter': function() {
        return '<b>Date: </b>' + Highcharts.dateFormat('%e-%b-%Y', new Date(this.x)) + '<br><b>' + $('#parameters option:selected').text() + ': </b>' + parseFloat(this.y.toFixed(3))
      }
    },
    'credits': {
      'text': 'EIDA WFCatalog (' + NODE + ')',
      'href': '',
    },
    'legend': {
      'enabled': false
    },
    'plotOptions': {
      'scatter': {
        'turboThreshold': false,
        'marker': {
          'color': "red",
          'radius': 2,
        }
      }
    },
    'series': [{
      'stream': stream,
      'name': 'Metrics',
      'color': '#C03',
      'data': data,
    }]
  });

}

/* fn addOption
 * Adds channel key to select box
 */
function addOption(key) {
  $("#channelCodes").append($("<option/>", {
    "value": key,
    "text": key
  }));
}

