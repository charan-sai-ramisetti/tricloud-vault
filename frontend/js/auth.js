function showError(message) {
  const box = document.getElementById("login-error");
  if (!box) return;
  box.innerHTML = message;
  box.style.display = "block";
}

document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("loginForm");
  if (!loginForm) return;

  const errorBox = document.getElementById("login-error");

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    errorBox.style.display = "none";
    errorBox.innerText = "";

    const email = loginForm.username.value.trim(); // email entered here
    const password = loginForm.password.value;

    // ✅ FIXED CHECK
    if (!email || !password) {
      showError("Email and password are required.");
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });

      let data = {};
      try {
        data = await response.json();
      } catch {}

      if (response.status === 401) {
        showError("Invalid email or password.");
        return;
      }

      if (response.status === 403) {
        showError(
          `Email not verified.
           <a href="resend-verification.html">Resend verification email</a>`
        );
        return;
      }

      if (!response.ok) {
        showError("Login failed. Please try again.");
        return;
      }

      // ✅ Success
      localStorage.setItem("access_token", data.access);
      localStorage.setItem("refresh_token", data.refresh);
      window.location.href = "../dashboard/dashboard.html";

    } catch (err) {
      showError("Login request failed. Please try again.");
    }
  });
});
