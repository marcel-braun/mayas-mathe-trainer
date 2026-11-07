(function () {
  var toggle = document.getElementById("coach-toggle");
  var panel = document.getElementById("rechenhilfe");
  if (toggle && panel) {
    toggle.addEventListener("click", function () {
      var open = panel.hasAttribute("hidden");
      if (open) {
        panel.removeAttribute("hidden");
      } else {
        panel.setAttribute("hidden", "");
      }
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) {
        panel.scrollIntoView({ block: "nearest" });
      }
    });
  }

  var keypad = document.querySelector(".keypad");

  function field() {
    var active = document.activeElement;
    if (active && active.classList && active.classList.contains("answer-input")) return active;
    return document.querySelector(".answer-input");
  }

  if (keypad) {
    keypad.addEventListener("click", function (event) {
      var button = event.target.closest("[data-key]");
      if (!button) return;
      var input = field();
      if (!input) return;
      var key = button.getAttribute("data-key");
      if (key === "back") {
        input.value = input.value.slice(0, -1);
      } else if (key === "," && input.value.indexOf(",") !== -1) {
        return;
      } else if (input.value.length < 14) {
        input.value += key;
      }
      input.focus();
    });
  }

  var orderInput = document.querySelector("#order-input");
  if (orderInput) {
    var buttons = Array.prototype.slice.call(document.querySelectorAll("[data-append]"));

    function picked() {
      return orderInput.value.split(",").map(function (part) {
        return part.trim();
      }).filter(Boolean);
    }

    function renderUsed() {
      var values = picked();
      buttons.forEach(function (button) {
        button.disabled = values.indexOf(button.getAttribute("data-append")) !== -1;
      });
    }

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var value = button.getAttribute("data-append");
        var current = orderInput.value.trim();
        orderInput.value = current ? current + ", " + value : value;
        renderUsed();
      });
    });

    var undo = document.querySelector("#order-undo");
    var clear = document.querySelector("#order-clear");
    if (undo) {
      undo.addEventListener("click", function () {
        var parts = orderInput.value.split(",");
        parts.pop();
        orderInput.value = parts.join(",").trim();
        renderUsed();
      });
    }
    if (clear) {
      clear.addEventListener("click", function () {
        orderInput.value = "";
        renderUsed();
      });
    }
    renderUsed();
  }
})();
