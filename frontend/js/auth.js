/* =========================
   LOGIN FUNCTION
   ========================= */
function login() {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  if (!email || !password) {
    alert("Email and password are required");
    return;
  }

  console.log("LOGIN PAYLOAD:", {
    username: email,
    password: password
  });

  fetch(`${API_BASE_URL}/auth/login/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      username: email,   // MUST be "username"
      password: password
    })
  })
    .then(res => res.json())
    .then(data => {
      console.log("LOGIN RESPONSE:", data);

      if (data.access) {
        localStorage.setItem("access_token", data.access);
        localStorage.setItem("refresh_token", data.refresh);
        window.location.href = "../dashboard/dashboard.html";
      } else {
        alert(data.error || "Login failed");
      }
    })
    .catch(err => {
      console.error(err);
      alert("Login request failed");
    });
}

/* =========================
   REGISTER FUNCTION
   ========================= */
function register() {
  const name = document.getElementById("name").value;
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  if (!name || !email || !password) {
    alert("All fields are required");
    return;
  }

  fetch(`${API_BASE_URL}/auth/register/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      username: name,   // Django User requires username
      email: email,     // REQUIRED for email verification
      password: password
    })
  })
    .then(res => res.json())
    .then(data => {
      alert("Registration successful. Please verify your email.");
      window.location.href = "login.html";
    })
    .catch(() => {
      alert("Registration failed. Please try again.");
    });
}
