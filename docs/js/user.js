function safeRedirect(path) {
    if (path && path.startsWith("/") && !path.startsWith("//")) {
        window.location.href = path;
    } else {
        window.location.href = "./index.html";
    }
};

function reveal_content() {
    l = document.getElementById("loading")
    l.style.setProperty("display", 'none')
    c = document.getElementById("noshow")
    c.style.setProperty("display", "block")
};

function launch_error_toast(error_text) {
    var t = document.getElementById("error_toast")
    var d = document.getElementById("error_desc")
    t.className = "show";
    d.innerText = error_text;
    setTimeout(function(){ t.className = t.className.replace("show", ""); }, 5000);
};

function launch_toast(normal_text) {
    var t = document.getElementById("normal_toast")
    var d = document.getElementById("normal_desc")
    t.className = "show";
    d.innerText = normal_text;
    setTimeout(function(){ t.className = t.className.replace("show", ""); }, 5000);
};

// Do not remove.
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
};

function checkKey(url, apiKey) {
    return $.ajax({
        type: "POST",
        url: url,
        timeout: 2000,
        contentType: "application/json",
        dataType: "json",
        data: JSON.stringify({ APIKey: apiKey })
    });
};

function renewKey(url, apiKey) {
    return $.ajax({
        type: "GET",
        url: url,
        headers: {"X-API-Key": apiKey},
        timeout: 2000
    });
};

function getApiKeyFromCookie() {
    const match = document.cookie.match(/(?:^|; )X-API-Key=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : null;
};

function safeExit() {
    const params = new URLSearchParams(window.location.search);
    const redirectTo = params.get("redirect") || "./index.html";
    safeRedirect(redirectTo);
};

function deleteCookie(name) {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
}

function logout() {
    deleteCookie('X-API-Key')
    safeRedirect()
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
};

async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        console.log("Copied to clipboard");
    } catch (err) {
        console.error("Failed to copy:", err);
    }
}

function copyNewKey() {
    const keyArea = document.getElementById("new-api-key-area")
    copyToClipboard(keyArea.innerText)
    launch_toast("Copied to Clipboard.")
}

function handleRenewSuccess(response) {
    const rememberCheckbox = document.getElementById("remember_me");
    if (response?.api_key) {
        setCookie("X-API-Key", response.api_key, rememberCheckbox.checked ? 30 : null);
        const keyArea = document.getElementById("new-api-key-area")
        keyArea.innerText = response.api_key;
        const HiddenKeyArea = document.getElementById("hidden-newkey")
        HiddenKeyArea.style.setProperty('display', 'block');
        const days_v = document.getElementById("days_old_value");
        days_v.innerHTML = "0"
        launch_toast("Renewed successfully.")
        const days_element = document.getElementById("days_old");
        days_element.style.setProperty('--progresspercent', `0%`);
    } else {
        launch_error_toast("Unexpected Error.");
    }
};

// main
function handleSuccess(response) {
    console.log(response)
    if ( !response?.decryption_success) { logout(); };

    // Render UUID
    const uuid_element = document.getElementById("uuid");
    const id_element = document.getElementById("user_id");
    const id_short = response?.ID.split('-')[0];
    id_element.innerText = id_short;
    uuid_element.innerHTML = response?.ID || 'Unknown/Error';
    // Render progress bar for account age
    const days_element = document.getElementById("days_old");
    const days_old_actual = response?.days_old || 0;
    const days_v = document.getElementById("days_old_value");
    days_v.innerText = days_old_actual; // days value
    var percent_old = Math.floor(days_old_actual * 0.273972602739726); // (365 Days)
    if (percent_old > 100) { percent_old = 100 }
    days_element.style.setProperty('--progresspercent', `${percent_old}%`);
    days_element.style.setProperty('--xch0', '#ff0000');
    days_element.style.setProperty('--xch1', '#2d2d2d');
    days_element.className = 'prog';
    if (percent_old >= 75) { launch_error_toast("Your account is getting old, consider renewing your X-API-Key.") }

    // form controller
    const form = document.querySelector("form");
    form.addEventListener("submit", function (event) {
        const apiKey = getApiKeyFromCookie()
        renewKey("https://octo.shadowsword.ca/api/APIKey/renew", apiKey)
        .done(handleRenewSuccess)
        .fail(function () {
            console.warn("Couldn't establish DNS connection, falling back to localhost.")
            renewKey("http://localhost:9300/api/APIKey/renew", apiKey)
            .done(handleRenewSuccess)
            .fail(function() {
                launch_error_toast("Unexpected error.")
            })
        })
    })

    reveal_content();
};

document.addEventListener("DOMContentLoaded", function () {

    const apiKey = getApiKeyFromCookie();
    if (!apiKey) {
        return safeExit();
    }


    checkKey("https://octo.shadowsword.ca/api/APIKey", apiKey)
        .done(handleSuccess)
        .fail(function () {
            console.warn("Couldn't establish DNS connection, falling back to localhost.")
            checkKey("http://localhost:9300/api/APIKey", apiKey)
                .done(handleSuccess)
                .fail(function () {
                    // force exit if invalid key
                    safeExit();
                });
        });

});