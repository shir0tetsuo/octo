function showHiddenButton(data) {
    if (data?.message == "OK") {
        document.getElementById("hidden-until-ok").style = 'display: block;'
    }
}

function updateTS_descript(e, prefix) {
    if (!e) return;

    // Read raw dataset value and coerce to a finite number (seconds)
    const raw = e.dataset?.ts;
    const rawNum = Number(raw);
    const ts = Number.isFinite(rawNum) ? rawNum * 1000 : 0;

    if (ts === 0) {
        e.innerHTML = "--:--:--:--";
    } else {
        let diff = (Date.now() - ts) / 1000;
        const days = Math.floor(diff / 86400);
        const hours = Math.floor((diff % 86400) / 3600);
        const minutes = Math.floor((diff % 3600) / 60);
        const seconds = Math.floor(diff % 60);
        e.innerHTML = `${prefix} ${days}d:${hours}h:${minutes}m:${seconds}s`;
    }

    requestAnimationFrame(() => updateTS_descript(e, prefix));
}

/**
 * Displays error notification toast at bottom of screen.
 * Auto-dismisses after 5 seconds.
 * 
 * @param {string} error_text - Error message to display
 */
function launch_error_toast(error_text) {
    var t = document.getElementById("error_toast")
    var d = document.getElementById("error_desc")
    t.className = "show";
    d.innerText = error_text;
    setTimeout(function(){ t.className = t.className.replace("show", ""); }, 5000);
}

/**
 * Toggle visibility of a DOM element (show/hide).
 * 
 * @param {boolean|undefined} b - true=show, false=hide, undefined=toggle
 * @param {string} layer - Element ID to toggle
 */
function _toggle(b, layer) {
    const d = document.getElementById(layer);
    if (b !== undefined) { 
        d.style.display = b ? 'block' : 'none';
    } else {
        d.style.display = (d.style.display === 'none') ? 'block' : 'none';
    }
}

function updateDescription(data, description) {
    const char_quote = '<i class="ri-server-line"></i> ';
    const char_quote_long = ' '+char_quote;
    while (description.replaceAll(char_quote_long, '').length < 1500) {
        description = description + char_quote_long + description;
    }
    document.getElementById("description").innerHTML =
        `${description}`;
    document.getElementById("statusbartag").textContent =
        `${data.version ?? "unknown"}`
}

function doHealthPost() {
    $.ajax({
        type: "GET",
        url: "https://octo.shadowsword.ca/api/health",
        timeout: 3000,
        dataType: "json",
        success: function (data) {
            console.log("Production");
            
            // Update with server started time
            const ts_area = document.getElementById('ts');
            ts_area.dataset.ts = data.application_ts;
            updateTS_descript(ts_area, '<i class="ri-history-line"></i> uptime')

            updateDescription(data, "Production");
            console.log(data);
            showHiddenButton(data);
            _toggle(false, 'loading')
            c = document.getElementById('card-main');
            c.style.setProperty('--spec-channel', '#008cffff');
            //updateStatus(data, "Octo");
        },
        error: function () {
            console.warn("Remote server unreachable, falling back to localhost");

            $.ajax({
                type: "GET",
                url: "http://localhost:9300/api/health",
                timeout: 6000,
                dataType: "json",
                success: function (data) {
                    console.log("Local server reachable");
                    console.log(data?.db_health);

                    // Update with server started time
                    const ts_area = document.getElementById('ts');
                    ts_area.dataset.ts = data.application_ts;
                    updateTS_descript(ts_area, '<i class="ri-history-line"></i> uptime')

                    updateDescription(data, "Local");
                    showHiddenButton(data);
                    _toggle(false, 'loading')
                    c = document.getElementById('card-main');
                    c.style.setProperty('--spec-channel', '#ffc400ff');
                    //updateStatus(data, "Local");
                },
                error: function () {
                    console.error('Server Com Failure')
                    description = 'Server unreachable.'
                    const char_quote = '<i class="ri-signal-wifi-error-line"></i> ';
                    const char_quote_long = ' '+char_quote;
                    while (description.replaceAll(char_quote_long, '').length < 1500) {
                        description = description + char_quote_long + description;
                    }
                    document.getElementById("description").innerHTML =
                        `${description}`;
                    launch_error_toast('Server unreachable. Try refresh.')
                    _toggle(false, 'loading')
                }
            });
        }
    });
}

document.addEventListener("DOMContentLoaded", function () {
    doHealthPost()
})