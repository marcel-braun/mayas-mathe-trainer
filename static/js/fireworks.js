(function () {
  var level = Number(document.body.dataset.feuerwerk || "0");
  var spark = Number(document.body.dataset.funken || "0");
  if (!level && !spark) return;

  var canvas = document.getElementById("feuerwerk");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var colors = ["#ffd15c", "#ef6a3c", "#12a594", "#6d5ef5", "#f26d9b", "#ffffff", "#7bdff2"];
  var particles = [];
  var alive = true;

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener("resize", resize);

  function burst(x, y, power) {
    var count = Math.round(28 * power);
    var index;
    for (index = 0; index < count; index += 1) {
      var angle = (Math.PI * 2 * index) / count + Math.random() * 0.25;
      var speed = (1.5 + Math.random() * 3.5) * Math.min(power, 2.3);
      particles.push({
        x: x,
        y: y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        g: 0.03 + Math.random() * 0.02,
        life: 48 + Math.random() * 30,
        age: 0,
        color: colors[index % colors.length],
        r: (2.4 + Math.random() * 3.6) * (power > 2 ? 1.3 : 1)
      });
    }
  }

  function rocket(power) {
    var x = window.innerWidth * (0.12 + Math.random() * 0.76);
    var y = window.innerHeight * (0.08 + Math.random() * 0.42);
    burst(x, y, power);
  }

  var delays = [160, 340, 560];
  var duration = 2600;
  if (level >= 3) {
    delays = [80, 180, 320, 500, 720, 980, 1280, 1600, 2000];
    duration = 4300;
  } else if (level === 2) {
    delays = [120, 280, 480, 760, 1080];
    duration = 3200;
  }

  if (level) {
    rocket(level);
  } else {
    burst(window.innerWidth * 0.5, window.innerHeight * 0.2, 0.85);
    duration = 1400;
  }

  if (reduce) {
    draw(false);
    return;
  }

  if (level) {
    delays.forEach(function (delay) {
      window.setTimeout(function () {
        if (alive) rocket(level);
      }, delay);
    });
  }

  function draw(moving) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    var next = [];
    var index;
    for (index = 0; index < particles.length; index += 1) {
      var particle = particles[index];
      if (moving) {
        particle.age += 1;
        if (particle.age >= particle.life) continue;
        particle.vy += particle.g;
        particle.x += particle.vx;
        particle.y += particle.vy;
      }
      ctx.globalAlpha = moving ? Math.max(0, 1 - particle.age / particle.life) : 1;
      ctx.fillStyle = particle.color;
      ctx.beginPath();
      ctx.arc(particle.x, particle.y, particle.r, 0, Math.PI * 2);
      ctx.fill();
      next.push(particle);
    }
    ctx.globalAlpha = 1;
    particles = next;
  }

  function frame() {
    if (!alive) return;
    draw(true);
    window.requestAnimationFrame(frame);
  }
  window.requestAnimationFrame(frame);
  window.setTimeout(function () {
    alive = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }, duration);
})();
