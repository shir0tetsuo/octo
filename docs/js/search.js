let number_of_zones = 16;

/**
 * Make AJAX request to fetch ownership rows from the server.
 * This is used for the ownership section.
 * Zone is added to the URL, not the query.
 * 
 */
function QueryOwnershipData(url, ownership_id, z, after_index=null) {

    const payload = {
        ownership: ownership_id,
        zone: z,
        ...(after_index !== null && { after_index })
    };

    return $.ajax({
        type: "POST",
        url: url,
        timeout: 2000,
        contentType: "application/json",
        dataType: "json",
        data: JSON.stringify(payload)
    })
}

function ChangeUserNav(res) {
    nav = document.getElementById('user-login-nav');
    if (res.user_context.decryption_success) {
        redirect = encodeURIComponent(window.location.pathname + window.location.search);
        nav.href = 'user.html?redirect=' + redirect; // This will point to the user page
        nav.innerHTML = '<i class="ri-passport-fill"></i> ' + String(res.user_context.ID).split('-')[0];
    } else {
        nav.href = `login.html?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`;
    }
}

function getApiKeyFromCookie() {
    const match = document.cookie.match(/(?:^|; )X-API-Key=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : null;
}

document.addEventListener("DOMContentLoaded", function () {
    const apiKey = getApiKeyFromCookie();

})