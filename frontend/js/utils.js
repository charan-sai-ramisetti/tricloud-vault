// Get access token
function getAccessToken() {
  return localStorage.getItem("access_token");
}

// Logout user
function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  window.location.href = "../auth/login.html";
}

// Protect dashboard (auto logout if no token)
(function protectRoute() {
  const token = getAccessToken();
  if (!token) {
    window.location.href = "../auth/login.html";
  }
})();

// Common auth headers
function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${getAccessToken()}`
  };
}
