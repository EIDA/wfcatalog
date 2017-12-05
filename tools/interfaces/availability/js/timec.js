var TimeCalendar = function(options) {

  this.availableColor ='rgba(119, 191, 152, 1)';
  this.gapColor = 'rgba(191, 119, 152, 1)';
  this.overlapColor = 'rgba(119, 152, 191, 1)'

  this.div = document.getElementById(options.id);
  this.canvas = document.createElement('canvas');

  this.textBox = document.createElement('div');
  this.titleBox = document.createElement('div');
  this.textBox.innerHTML = '<br>';
  this.textBox.style.color = '#888';

  this.div.appendChild(this.canvas);
  this.ctx = this.canvas.getContext("2d");

  this.blockSpace = 6;

  this.barHeight = 25;

  this.paddingTop = 20;
  this.canvas.height = this.paddingTop + this.barHeight + 50;
  this.paddingLeft = 50;
  this.paddingRight = 50;
  this.day = options.day;

  this.MINUTES_PER_HDAY = 60 * 12;
  this.canvas.width = this.MINUTES_PER_HDAY + this.paddingLeft + this.paddingRight;

  var self = this;

  // Hook up a listener for hovers and clicks
  this.canvas.addEventListener('mousemove', function(evt) {
    self.MouseHover(evt);
  });

  this.setAvailability(options.data);

  this.Draw();

}

TimeCalendar.prototype.setAvailability = function(data) {

  // Initially full red bar
  this.ctx.fillStyle = this.gapColor;
  this.ctx.fillRect(this.paddingLeft, this.paddingTop, this.MINUTES_PER_HDAY, this.barHeight);

  var occupied = null;

  for(var i = 0; i < data.length; i++) {

    var start = this.ParseTime(data[i].start_time, 'start');
    var end = this.ParseTime(data[i].end_time, 'end');

    if(occupied === null) {
      this.ctx.fillStyle = this.availableColor;
      this.ctx.fillRect((this.paddingLeft + start), this.paddingTop, (end - start), this.barHeight);
      occupied = end;
      continue;
    }

    if(start < occupied) {
      var min = Math.min(occupied, end);

      this.ctx.fillStyle = this.overlapColor;
      this.ctx.fillRect((this.paddingLeft + start), this.paddingTop, min - start, this.barHeight);
    
    }

    if(end > occupied) {
      var max = Math.max(occupied, start);
       
      this.ctx.fillStyle = this.availableColor;
      this.ctx.fillRect((this.paddingLeft + max), this.paddingTop,  end - max, this.barHeight);

    }

    occupied = end;
   

  }

}

TimeCalendar.prototype.MouseHover = function(evt) {

  var rect = this.canvas.getBoundingClientRect();

  var x = evt.clientX - rect.left;


}

TimeCalendar.prototype.xToTime = function(x) {

  x -= 0.5 * this.paddingLeft;

  var g = x / 30;
  var H = Math.floor(g) - 1;
  console.log(H);
  var y = (x * 2) % 60;
  var M = Math.floor(y);
  console.log(M);
  return new Date(2016, 0, this.day, H, M);

}

TimeCalendar.prototype.PixelOffset = function(time) {
  return Math.round(time.H * 30 + (time.M / 2));

}

TimeCalendar.prototype.ParseTime = function(str, which) {

  var offset = this.PixelOffset({
    'H': Number(str.substring(11, 13)),
    'M': Number(str.substring(14, 16)),
    'S': Number(str.substring(17, 19))
  });

  if(new Date(str).getDate() !== this.day) {
    return this.MINUTES_PER_HDAY;
  }

  return offset;

}

TimeCalendar.prototype.Draw = function() {

  this.ctx.strokeStyle = 'rgb(138, 109, 59)';
  this.ctx.lineWidth = 1;
  this.ctx.rect(this.paddingLeft -0.5, 0.5 + this.paddingTop, this.MINUTES_PER_HDAY, this.barHeight);
  this.ctx.stroke();

  this.ctx.fillStyle = "rgb(138, 109, 59)";
  this.ctx.font = "bold 14px Calibri";
  // Draw tick marks
  this.ctx.strokeStyle = 'rgb(138, 109, 59)';
  this.lineWidth = 1;
  for(var i = 0; i < 25; i++) {
  this.ctx.beginPath();
    this.ctx.moveTo(this.paddingLeft + i * this.MINUTES_PER_HDAY / 24 - 0.5, this.barHeight + this.paddingTop);
    this.ctx.lineTo(this.paddingLeft + i * this.MINUTES_PER_HDAY / 24 - 0.5, this.barHeight + 5 + this.paddingTop);
    this.ctx.fillText(("0" + i).slice(-2), this.paddingLeft + i * this.MINUTES_PER_HDAY / 24 - 7, this.barHeight + 20 + this.paddingTop);
    this.ctx.stroke();
  }
  
}
