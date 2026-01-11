function safeRedirect(path) {
    if (path && path.startsWith("/") && !path.startsWith("//")) {
        window.location.href = path;
    } else {
        window.location.href = "./index.html";
    }
}

function launch_error_toast(error_text) {
    var t = document.getElementById("error_toast")
    var d = document.getElementById("error_desc")
    t.className = "show";
    d.innerText = error_text;
    setTimeout(function(){ t.className = t.className.replace("show", ""); }, 5000);
}

document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector("form");
    const apiKeyInput = form.querySelector('input[placeholder="X-API-Key"]');
    const rememberCheckbox = document.getElementById("remember_me");
    const servermsgbox = document.getElementById("servermessage");

    function showServerMessage(msg) {
        servermsgbox.textContent = msg;
        servermsgbox.style.display = "block";
    }

    function setCookie(name, value, days) {
        let expires = "";
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = "; expires=" + date.toUTCString();
        }
        const isHttps = location.protocol === "https:";
        document.cookie =
            name + "=" + encodeURIComponent(value) +
            expires +
            "; path=/; SameSite=Strict" +
            (isHttps ? "; Secure" : "");
    }

    function checkKey(url, apiKey) {
        return $.ajax({
            type: "POST",
            url: url,
            timeout: 2000,
            contentType: "application/json",
            dataType: "json",
            data: JSON.stringify({ APIKey: apiKey })
        });
    }

    form.addEventListener("submit", function (event) {
        event.preventDefault();

        const apiKey = apiKeyInput.value.trim();
        if (!apiKey) {
            showServerMessage("Please enter an API Key");
            return;
        }

        checkKey("https://octo.shadowsword.ca/api/CheckAPIKey", apiKey)
            .done(handleSuccess)
            .fail(function () {
                console.warn("Couldn't establish DNS connection, falling back to localhost.")
                checkKey("http://localhost:9300/api/CheckAPIKey", apiKey)
                    .done(handleSuccess)
                    .fail(function () {
                        showServerMessage("Cannot establish connection.");
                        launch_error_toast("Cannot establish server connection.")
                    });
            });

        function handleSuccess(response) {
            if (response?.valid_key) {
                setCookie("X-API-Key", apiKey, rememberCheckbox.checked ? 30 : null);
                const params = new URLSearchParams(window.location.search);
                const redirectTo = params.get("redirect") || "./index.html";
                safeRedirect(redirectTo);
            } else {
                showServerMessage("This is not a valid key.");
            }
        }
    });
});