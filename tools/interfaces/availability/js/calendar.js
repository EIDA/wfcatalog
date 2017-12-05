/*
 *
 * Calendar class for displaying channel availabilities
 * Copyright by Mathijs Koymans, 2016
 *
 */
var Calendar = function(options) {

  this.days = new Array();

  // Create a new canvas element and append it
  // to the passed options.id
  this.title = options.title;
  this.div = document.getElementById(options.id);
  this.canvas = document.createElement('canvas');

  this.textBox = document.createElement('div');
  this.titleBox = document.createElement('div');
  this.textBox.innerHTML = '<br>';
  this.textBox.style.color = '#888';

  this.net = options.net;
  this.sta = options.sta;
  var s = options.cha.split(".");
  this.cha = s[s.length - 1];
  this.loc = s.length === 2 ? s[0] : '--';

  this.div.appendChild(this.titleBox);
  this.div.appendChild(this.canvas);
  this.div.appendChild(this.textBox);
  
  this.ctx = this.canvas.getContext("2d");

  // Some options
  this.textColor = '#999';
  this.blockSpace = 12;
  this.offsetLeft = this.blockSpace;
  this.offsetRight = this.blockSpace;
  this.offsetTop = this.blockSpace;
  this.height = 7 * this.blockSpace + 6 + this.offsetTop;

  this.HOVER_COLOR = '#fafafa';

  this.canvas.width = this.offsetLeft + 54 * (this.blockSpace + 1) + this.offsetRight;
  this.canvas.height = this.height + (2 * this.blockSpace);

  // Create a rainbow Class
  this.Rainbow = new Rainbow().setSpectrum(
    'FF8A8A', 'FF8D8A', 'FF918A', 'FF958A',
    'FF988A', 'FF9C8A', 'FFA08A', 'FFA48A',
    'FFA78A', 'FFAB8A', 'FFAF8A', 'FFB28A',
    'FFB68A', 'FFBA8A', 'FFBE8A', 'FFC18A',
    'FFC58A', 'FFC98A', 'FFCC8A', 'FFD08A',
    'FFD48A', 'FFD88A', 'FFDB8A', 'FFDF8A',
    'FFE38A', 'FFE68A', 'FFEA8A', 'FFEE8A',
    'FFF28A', 'FFF58A', 'FFF98A', 'FFFD8A',
    'FDFF8A', 'F9FF8A', 'F5FF8A', 'F2FF8A',
    'EEFF8A', 'EAFF8A', 'E6FF8A', 'E3FF8A',
    'DFFF8A', 'DBFF8A', 'D8FF8A', 'D4FF8A',
    'D0FF8A', 'CCFF8A', 'C9FF8A', 'C5FF8A',
    'C1FF8A', 'BDFF8A', 'BAFF8A', 'B6FF8A',
    'B2FF8A', 'AFFF8A', 'ABFF8A', 'A7FF8A',
    'A3FF8A', 'A0FF8A', '9CFF8A', '98FF8A',
    '95FF8A', '91FF8A', '8DFF8A', '8AFF8A'
  );

  var self = this;

  // Hook up a listener for hovers and clicks
  this.canvas.addEventListener('mousemove', function(evt) {
    self.MouseHover(evt);
  });

  this.canvas.addEventListener('mouseout', function(evt) {
    if(self.previous) {
      self.previous.Draw();
    }
    self.tooltip('<br>');
  });

  this.canvas.addEventListener('click', function(evt) {
    self.getClickedDay(evt);
  });

  this.setYear(options.year);
  this.setAvailability(options.data);

  // Draw the calendar
  this.Draw();

}

/*
 * Calendar.Tooltip
 * Sets the text of the tooltip
 */
Calendar.prototype.tooltip = function(str) {

  this.textBox.innerHTML = '<i>' + str + '</i>';

}

/*
 * Calendar.Click
 * Set the callback
 */
Calendar.prototype.click = function(callback) {
  this.clickCallback = callback;
}

Calendar.prototype.getClickedDay = function(evt) {

  var instance = this.getDayInstance(evt);

  if(!instance || !instance.hasData) {
    return;
  }

  // Bind the day instance to the callback
  if(typeof(this.clickCallback) === 'function' && this.clickCallback) {
    this.clickCallback.bind(instance)();
  }

}

/*
 * Calendar.GetDayInstance
 */
Calendar.prototype.getDayInstance = function(evt) {

  // Get the bounding rectangle of the canvas and determine
  // the x, y coordinates of the mouse pointer
  var rect = this.canvas.getBoundingClientRect();

  var x = evt.clientX - rect.left;
  var y = evt.clientY - rect.top;

  // Determine the week of year and day of week by counting pixels
  var weekOfYear = Math.floor((x - this.offsetLeft) / (this.blockSpace + 1));
  var dayOfWeek = Math.floor((y - this.offsetTop) / (this.blockSpace + 1));

  if(weekOfYear < 0 || weekOfYear > (this.isLeap ? 53 : 52) || dayOfWeek < 0 || dayOfWeek > 6) {
    return null;
  }

  // Confirm hovering over a valid day on the calendar
  // Determine the day of year
  var dayOfYear = (7 * weekOfYear) + dayOfWeek - this.dayOffset;
  if(dayOfYear < 0 || dayOfYear > (this.nDays - 1)) {
    return null;
  }

  // Return the day object beloning to this day
  return this.days[dayOfYear];

}

/*
 * Calendar.MouseHover
 * event when mouse is moved over calendar
 */
Calendar.prototype.MouseHover = function(evt) {

  // Get the day instance beneath the mouse pointer
  var dayObj = this.getDayInstance(evt);

  // Redraw the previous
  if(this.previous) {
    this.previous.Draw();
  }

  // If there is no day instance, the user is
  // hovering outside of the calendar days
  if(!dayObj) {
    this.tooltip('<br>'); return;
  } else if(dayObj.isToday()) {
    this.tooltip(dayObj.dateObject.toISOString().substring(0, 10) + ' - Metrics for today will be available tomorrow'); return;
  } else if(!dayObj.hasData) {
    this.tooltip(dayObj.dateObject.toISOString().substring(0, 10) + ' - Metrics are unavailable'); return;
  } else {
    this.tooltip(dayObj.text);
  }

  // Create a day replica of the day
  // being hovered over
  this.previous = dayObj.Replica();

  // Redraw the day being hovered over
  // with the hover color
  dayObj.currentColor = this.HOVER_COLOR;
  dayObj.Draw();

}

Calendar.prototype.setYear = function(year) {

  this.year = Number(year);

  // Determine whether this year is a leap year
  // And set the amount of days in a year
  this.isLeap = ((year % 4) === 0 && ((year % 100) !== 0 || (year % 400) === 0));
  this.nDays = this.isLeap ? 366 : 365;

  this.SetDayOffset();
  this.setMonths();

}

Calendar.prototype.writeFullAvailability = function() {

  this.titleBox.innerHTML = '<h3><b><span class="orfeus-red">' + this.year + '</span></b> ' + this.title + ' </h3><small>Average yearly availability over ' + this.nDaysUsed + ' available days: <b>' + Number(this.totalAvailability.toFixed(3)) + '%</b></small>';

}

Calendar.prototype.setAvailability = function(days) {

  // Create an array of days in the given year
  // With an empty availability, later we will overwrite
  // Days with data
  for (var d = new Date(this.year, 0, 1, 1); d <= new Date(this.year + 1, 0, 1); d.setDate(d.getDate() + 1)) {
    this.days.push(new Day({'day': d, 'availability': null}, this));
  }

  // Replace empty days with days that have data
  for(var i = 0; i < days.length; i++) {
    var day = new Day(days[i], this);
    this.days[day.index] = day;
  }

  this.nDaysUsed = 0;

  var availabilitySum = 0;
  for(var i = 0; i < this.days.length; i++) {
    if(this.days[i].hasData && this.days[i].values.availability !== null) {
      availabilitySum += this.days[i].values.availability; this.nDaysUsed++;
    }
  }

  this.totalAvailability = this.nDaysUsed === 0 ? 0 : availabilitySum / this.nDaysUsed;
  this.nDaysMissing = this.nDays - this.nDaysUsed;

}

Calendar.prototype.DrawMonthBoundaries = function() {

  this.ctx.strokeStyle = '#999';

  // Draw the boundary line left of Jan
  var sumDays = this.dayOffset;
  this.DrawMonthLine(sumDays);
  this.monthNameSpacing = this.offsetLeft;

  // Loop over all months to draw name and right boundary
  // The sum of days is required to determine carry the
  // end of a month to the next
  for(var i = 0; i < this.months.length; i++) {
    var month = this.months[i];
    sumDays += month.days;
    this.DrawMonthName(sumDays, month);
    this.DrawMonthLine(sumDays);
  }

}

Calendar.prototype.DrawDays = function () {

  // Monday - Sunday day abbrevations
  var DAY_ABBREVATIONS = [
    'M',
    'T',
    'W',
    'T',
    'F',
    'S',
    'S'
  ];

  var MAGIC_PADDING = 2;
  this.ctx.fillStyle = this.textColor;
  this.ctx.font = "bold 11px Nimbus Sans L"

  // Write the day names
  for(var i = 0; i < 7; i++) {
    this.ctx.fillText(DAY_ABBREVATIONS[i], 0, this.blockSpace + i * (this.blockSpace + 1) - MAGIC_PADDING + this.offsetTop);
  }

}

/*
 * Day class
 */
Day = function(options, Calendar) {

  // Reference to the parent calendar
  this.Calendar = Calendar;
  this.dateObject = new Date(options.day);
  this.start = this.dateObject.toISOString();
  this.end = new Date(this.dateObject.getTime() + (24 * 60 * 60 * 1000)).toISOString();
  this.id = options.id

  // Return if the day does not fall within the year
  if(this.dateObject.getFullYear() !== this.Calendar.year) {
    return;
  }

  this.values = options;
  this.hasData = Boolean(options.availability)
  this.day = this.Doy(this.dateObject);

  // Correct for a day offset
  this.index = this.day - 1;
  this.correctedDay = this.index + this.Calendar.dayOffset;

  if(this.isToday()) {
    this.color = '#D9ECFF';
  } else if(this.values.availability === null) {
    this.color = '#ededed';
  } else {
    this.color = this.Color();
    this.text = this.Text();
  }

  // Set the day of week
  this.dayOfWeek = this.correctedDay % 7;
  this.weekOfYear = Math.ceil(this.correctedDay / 7);

  if(this.dayOfWeek === 0) {
    this.weekOfYear++;
  }

  this.xPixels = this.weekOfYear * (this.Calendar.blockSpace + 1) - 1;
  this.yPixels = this.dayOfWeek * (this.Calendar.blockSpace + 1) + this.Calendar.offsetTop;

  this.currentColor = this.color;
  this.continuous = this.values.availability === 100;
  this.symbol = this.continuous ? '\u2605' : ''
  
}

Day.prototype.isToday = function() {
  return this.dateObject.toDateString() === new Date().toDateString();
}

/*
 * Day Replica
 * returns replica of a day instance
 */
Day.prototype.Replica = function() {
  return new Day(this.values, this.Calendar);
}

Day.prototype.Doy = function(d) {

  var start = new Date(d.getFullYear(), 0, 0);

  var diff = d - start;
  var oneDay = 1000 * 60 * 60 * 24;
  return Math.floor(diff / oneDay);

}

/*
 * Day.GetText
 */
Day.prototype.Text = function() {
  return this.dateObject.toISOString().substring(0, 10) + ' - Availability: <b>' + Number(this.values.availability.toFixed(3)) + '%</b>';
}

/*
 * Day.Color
 * Determine the color based on the given value
 */
Day.prototype.Color = function() {
  return '#' + this.Calendar.Rainbow.colourAt(this.values.availability);
}

/*
 * Day.Draw
 * Draws a day instance on the calendar
 */
Day.prototype.Draw = function() {

  // Draw the day rectangle
  this.Calendar.ctx.fillStyle = this.currentColor;

  this.Calendar.ctx.fillRect(
    this.xPixels,
    this.yPixels,
    this.Calendar.blockSpace,
    this.Calendar.blockSpace
  );

  var FONT = "9px Nimbus Sans L";

  // If the day has a symbol, we draw it
  // if the day is unavailable we will put an x (\u00d7)
  if(this.hasData) {
    this.Calendar.ctx.fillStyle = '#00DD00'
    this.Calendar.ctx.font = FONT;
    this.Calendar.ctx.fillText(this.symbol, this.xPixels + 2, this.yPixels + 9);
  }

}

/*
 * Calendar.DrawMonthName
 * Writes name of the month below a month section
 * on the calendar
 */
Calendar.prototype.DrawMonthName = function(sumDays, month) {

  var monthOffset = (sumDays - month.days) % 7;
  var MAGIC_PADDING = 8;

  // Determine the factor to offset the text by
  // to center it. This is some mumbo-jumbo 
  var factor = (monthOffset + month.days) > 34 ? 5 : 4;
  this.ctx.fillStyle = "#888";
  this.ctx.font = "bold 11px Nimbus Sans L"
  this.monthNameSpacing += 0.5 * factor * (this.blockSpace + 1);
  this.ctx.fillText(month.name, this.monthNameSpacing - MAGIC_PADDING, this.height + 2 + this.blockSpace);
  this.monthNameSpacing += 0.5 * factor * (this.blockSpace + 1);
  
}

/*
 * Calendar.setMonths
 * Sets the months and days for a year
 */
Calendar.prototype.setMonths = function () {

  this.months = [
    {'days': 31, 'name': 'Jan'},
    {'days': (this.isLeap ? 29 : 28), 'name': 'Feb'},
    {'days': 31, 'name': 'Mar'},
    {'days': 30, 'name': 'Apr'},
    {'days': 31, 'name': 'May'},
    {'days': 30, 'name': 'Jun'},
    {'days':  31, 'name': 'Jul'},
    {'days':  31, 'name': 'Aug'},
    {'days':  30, 'name': 'Sep'},
    {'days':  31, 'name': 'Oct'},
    {'days':  30, 'name': 'Nov'},
    {'days':  31, 'name': 'Dec'}
  ];

}

/*
 * Calendar.DrawMonthLine
 * Draws individual month boundaries based on the sum
 * of days after N months
 */
Calendar.prototype.DrawMonthLine = function(sumDays) {

  // The determine the week of year and day of week
  var weekOfYear = Math.ceil(sumDays / 7);
  var dayOfWeek = sumDays % 7;

  // Start and end coordinate
  var startX = (this.offsetLeft + weekOfYear * (this.blockSpace + 1) - 0.5);
  var endX = startX - (this.blockSpace + 1);
  var bendY = dayOfWeek * (this.blockSpace + 1) - 0.5 + this.offsetTop;

  // Begin the path and move to the start
  this.ctx.beginPath();
  this.ctx.moveTo(startX, this.offsetTop - 1);

  // If a week fills a month, go straight down
  // otherwise bend at the month boundary and finish straight down
  if(dayOfWeek === 0) {
    this.ctx.lineTo(startX, this.height);
  } else {
    this.ctx.lineTo(startX, bendY);
    this.ctx.lineTo(endX, bendY);
    this.ctx.lineTo(endX, this.height);
  }

  this.ctx.stroke();
  this.ctx.closePath();

}

/*
 * Calendar.CleanCanvas
 * Fully clears the canvas
 */
Calendar.prototype.CleanCanvas = function () {
  this.ctx.clearRect(0, 0, this.ctx.canvas.width, this.ctx.canvas.height);
}

/*
 * Calendar.Draw
 * Draw the calendar
 */
Calendar.prototype.Draw = function() {

  this.CleanCanvas();

  // Draw the calendar edges
  this.DrawBoundaries();
  this.DrawMonthBoundaries();

  // Write the abbrevated daynames and title on canvas
  this.DrawDays();

  // Draw all individual days in the year
  for(var i = 0; i < this.days.length; i++) {
    this.days[i].Draw();
  }

}

/*
 * Calendar.SetDayOffset
 * determines the day offset from Monday
 */
Calendar.prototype.SetDayOffset = function() {

  this.first = new Date(this.year, 0, 1, 1, 0, 0).getUTCDay();
  this.dayOffset = this.first === 0 ? 6 : this.first - 1;

}

/*
 * Calendar.DrawBoundaries
 * Draws the top and bottom calendar boundaries
 */
Calendar.prototype.DrawBoundaries = function () {

  this.writeFullAvailability();

  // Start drawing at the top right, we must
  // determine the initial offset as a year might 
  // not start on Monday and be oddly shaped
  var offset = this.offsetLeft + (this.dayOffset ? this.blockSpace : 0);

  // Draw the path from (offset) top to bottom
  this.ctx.beginPath();
  this.ctx.moveTo(offset, this.offsetTop - 0.5);
  this.ctx.strokeStyle = '#888';

  // Determine the number of weeks (columns) in the calendar
  var nWeeks = Math.ceil((this.dayOffset + this.nDays) / 7) + 1;

  // Move over the top of the calendar and cover all columns
  this.ctx.lineTo(nWeeks * (this.blockSpace + 1) - 1, this.offsetTop - 0.5);


  // Draw the bottom
  this.ctx.moveTo(this.offsetLeft - 1, this.height + 0.5);
  var nWeeks = Math.floor((this.dayOffset + this.nDays) / 7) + 1;
  this.ctx.lineTo(nWeeks * (this.blockSpace + 1) - 1, this.height + 0.5);

  this.ctx.stroke();
  this.ctx.closePath();
  
}
