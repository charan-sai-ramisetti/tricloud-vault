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

    if (errorBox) {
  errorBox.style.display = "none";
  errorBox.innerText = "";
}


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

// =========================
// REGISTER FUNCTION
// =========================
function register() {
  const username = document.getElementById("name").value.trim();
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  if (!username || !email || !password) {
    alert("All fields are required");
    return;
  }

  fetch(`${API_BASE_URL}/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: username,
      email: email,
      password: password
    })
  })
    .then(async res => {
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        alert(data.error || "Registration failed");
        return;
      }

      alert("Registration successful. Please verify your email.");
      window.location.href = "login.html";
    })
    .catch(() => {
      alert("Registration request failed. Please try again.");
    });
}

