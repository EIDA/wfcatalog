// Add color to ORFEUS title menu
$('#data').addClass('active');
$('#menu_data .available').addClass('active')

// Globals
var cache, channelCodes;
var WFCATALOG_ADDRESS = "https://www.orfeus-eu.org/eidaws/wfcatalog/1/query";
var ENABLE_SUGGESTIONS = false;

$("#network").val(getParameterByName("net"))
$("#station").val(getParameterByName("sta"))
$("#dateMin").val(getParameterByName("start"));
$("#dateMax").val(getParameterByName("end"))

$(function () {

  if(ENABLE_SUGGESTIONS) {
    $("#station").typeahead({
      "minlength": 0,
      "items": 10,
      "source": function(query, process) {

        var network = $("#network").val();

        if(network === "") {
          return new Array();
        }

        return $.get("./scripts/filter-by.php", {"network": network}, function(json) {
          process(json.sort());
        });

      }

    });

    // Network typeahead
    $("#network").typeahead({
      "minLength": 0,
      "showHintOnFocus": true,
      "items": 10,
      "source": function(query, process) {
        return $.get("./scripts/filter-by.php", {}, function(json) {
          process(json.sort());
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

  // Submit the Ajax request to the WFCatalog
  $("#request").click(function () {

    $("#calendars").html("");
    $("#infoContainer").hide();

    // Get the user input
    var net = $('#network').val();
    var sta = $('#station').val();
    var start = $('#dateMin').val();
    var end = $('#dateMax').val();

    // Need all parameters
    if(!net || !sta || !start || !end) {
      $("#infoContainer").show();
      return $("#chartInformation").html("Fill in all request parameters.");
    }

    // Stop if user supplies wildcards
    if(!/^[a-zA-Z0-9]+$/.test(sta) || !/^[a-zA-Z0-9]+$/.test(net)) {
      $("#infoContainer").show();
      return $("#chartInformation").html("Invalid station or network input");
    }

    // Hide/Show DOM elements
    progressVisible(true);
    controlsVisible(false);

    // URL for the request
    var url = '?include=sample&net=' + net + '&sta=' + sta + '&start=' + start + '&end=' + end + '&cha=HG?,?H?,?DF';

    $.ajax({
      'type': 'GET',
      'error': function(error) {
        $("#infoContainer").show();
        progressVisible(false);
        $("#chartInformation").html("<b>OOPS! The WFCatalog returned the following error: </b><br><br>" + error.responseText.replace(/\n/g, "<br>"));
      },
      'url': WFCATALOG_ADDRESS + url,
      'success': function(json) {

        $("#infoContainer").show();
        progressVisible(false);

        if(!json) {
          return $("#chartInformation").html("No metrics were found for this request.");
        }

        // Create a cache so we can show different streams without
        // having to go back to the catalogue
        dataCache = new Object();

        // Collect the channels in an associative array
        var docChan;
        for(var i = 0; i < json.length; i++) {
          docChan = json[i].location ? json[i].location + "." + json[i].channel : json[i].channel;
          if(!dataCache.hasOwnProperty(docChan)) {
            dataCache[docChan] = new Array();
          }
          dataCache[docChan].push({
            'availability': json[i].percent_availability,
            'day': json[i].start_time
          });

        }

        // Empty the channel selector
        $("#channelCodes").empty();

        // Collect all channels
        channelCodes = new Array();

        for(var key in dataCache) {
          channelCodes.push(key);
        }

        channelCodes.sort();
        for(var i = 0; i < channelCodes.length; i++) {
          addOption(channelCodes[i]);
        }

        controlsVisible(true);

        cache = dataCache;

        createCalendars();

        }

      });

    });

  // Any trigger is hit, redraw calendars
  $(".trigger").change(function() {
    createCalendars();
  });

});


/*
 * Function createCalendars
 *
 * Creates calendars from cached availability data
 * for a given stream for N years
 *
 */
function createCalendars() {
 
  // Clean-up
  $("#calendars").html("");

  // Get all values requested for calendar
  var cha = $("#channelCodes").val();
  var net = $("#network").val();
  var sta = $("#station").val();

  var start = $("#dateMin").val();
  var end = $('#dateMax').val();

  var startYear = new Date(start).getFullYear();
  var endYear = new Date(end).getFullYear();

  // Write some information to DOM
  var text = [
    "Yearly calendars showing availability for ",
    "<b>" + net + "." + sta + "." + cha + "</b>",
    "between",
    "<b>" + new Date(start).toISOString().substring(0, 10) + "</b>",
    "and",
    "<b>" + new Date(end).toISOString().substring(0, 10) + "</b>.",
    "<p><small><span style='color: #00DD00;'>\u2605</span> indicates full channel availability</small>"
  ].join(" ");

  $("#chartInformation").html(text);

  // Create a calendar for each year
  for(var year = startYear; year <= endYear; year++) {

    // Check the data cache
    if(cache[cha]) {
      var data = cache[cha].filter(function(x) {
        return new Date(x.day).getFullYear() === year
      });
    }

    // Create a new calendar instance
    var c = new Calendar({
      "id": "calendars",
      "year": year,
      "net": net,
      "sta": sta,
      "cha": cha,
      "title": [net, sta, cha].join("."),
      "data": data
    });
    
    // Callback when a day tile is clicked
    c.click(function() {
    
      if(this.continuous) return;

      var dateC = this.dateObject;
      var day = this.dateObject.getDate();
      var availability = this.values.availability;

      var url = '?csegments=true&net=' + this.Calendar.net + '&sta=' + this.Calendar.sta + '&cha=' + this.Calendar.cha + '&start=' + this.start + '&end=' + this.end;

      // AJAX request for continuous segments
      $.ajax({
        "dataType": "JSON",
        "type": "GET",
        "error": function(error) {
          $("#chartInformation").html("No continuous segments were found for this request.");
        },
        "url": WFCATALOG_ADDRESS + url,
        "success": function(json) {

          // Should be a single document returned
          var document = json[0];

          // Check if we have continuous segments; it may be that the trace is continuous
          // and this property does not exist
          if(document['c_segments']) {

            // Make sure the segments are sorted by start
            document['c_segments'].sort(function(a, b) {
              return new Date(a.start_time) - new Date(b.start_time);
            });

            // Empty the canvas for where the continuous segment is drawn
            $("#segmentLine").html("");

            // Map segments to write some segment text
            var text = document['c_segments'].map(function(segment) {
              return "<b>" + segment.start_time + "</b> to <b>" + segment.end_time + "</b>";
            }).join("<br>");

            // Create a new time calendar from the sorted list of continuous segments
            var k = new TimeCalendar({
              'id': 'segmentLine',
              'day': day,
              'data': document['c_segments']
            });
 
            // Write some information to the DOM
            $("#segmentTitle").html("Continuous Segments for <b>" + dateC.toISOString().substring(0, 10) + "</b><p>(" + parseFloat(availability.toFixed(3)) + " % available)");
            $("#segmentText").html("<h4> " + document['c_segments'].length + " available segment" + (document['c_segments'].length > 1 ? "s" : "") + ":</h4> " + text);

            $("#msiModal").modal();

          }

        }

      });

    });

  }

}

/* fn setStations
 * Sets typeahead stations for input network
 */
function setStations(network) {

  if(!statObj.hasOwnProperty(network)) {
    return $('#station').data('typeahead').source = new Array();
  }

  var stations = new Array();
  for(var key in statObj[network]) {
    stations.push(key);
  }

  $('#station').data('typeahead').source = stations.sort();
  
}

function addOption(key) {

  $("#channelCodes").append($("<option/>", {
    'value': key,
    'text': key
  }));

}

function getParameterByName(name, url) {
    if (!url) url = window.location.href;
    name = name.replace(/[\[\]]/g, "\\$&");
    var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)"),
        results = regex.exec(url);
    if (!results) return null;
    if (!results[2]) return '';
    return decodeURIComponent(results[2].replace(/\+/g, " "));
}
