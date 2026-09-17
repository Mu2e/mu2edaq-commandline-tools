(() => {
  const nav = document.querySelector(".site-nav");
  const toggle = document.querySelector(".nav-toggle");

  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  const page = document.body.dataset.page;
  if (page) {
    const current = document.querySelector(`[data-nav="${page}"]`);
    if (current) current.setAttribute("aria-current", "page");
  }

  const toast = document.querySelector(".toast");
  let toastTimer;
  const showToast = (message) => {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("visible"), 1500);
  };

  document.querySelectorAll(".code-block").forEach((block) => {
    const code = block.querySelector("code");
    if (!code) return;
    const button = document.createElement("button");
    button.className = "copy-button";
    button.type = "button";
    button.textContent = "Copy";
    button.setAttribute("aria-label", "Copy code to clipboard");
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(code.textContent);
        button.textContent = "Copied";
        showToast("Copied to clipboard");
        setTimeout(() => {
          button.textContent = "Copy";
        }, 1500);
      } catch {
        showToast("Select and copy the command manually");
      }
    });
    block.appendChild(button);
  });

  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", () => {
      if (nav) nav.classList.remove("open");
      if (toggle) toggle.setAttribute("aria-expanded", "false");
    });
  });
})();
