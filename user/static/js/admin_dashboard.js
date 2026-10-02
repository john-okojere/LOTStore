document.addEventListener("DOMContentLoaded", function() {
    const toggleBtn = document.getElementById("toggleBtn");
    const sidebar = document.getElementById("sidebar");
    const mainContent = document.querySelector(".main-content");

    toggleBtn.addEventListener("click", function() {
        sidebar.classList.toggle("hidden");
        mainContent.classList.toggle("full");
    });
});
