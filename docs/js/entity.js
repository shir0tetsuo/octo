
// ============================================================================
// OCTO ENTITY VIEWER - Frontend Display Logic
// ============================================================================
// This page displays a single "Entity" which is a versioned object stored in
// a spatial database. Entities exist at coordinates (x, y, zone) and can have
// multiple iterations/versions. Iteration #0 is the genesis version that must
// be minted (committed to DB) before additional iterations can be created.
// ============================================================================

// ──── Global State Variables ────────────────────────────────────────────────
let number_of_zones = 8;

const container = document.getElementById('container');

// Entity versioning system: { 0: genesis_entity, 1: updated_entity, ... }
// Keys are iteration numbers, values are entity data objects from the server
var entity;
// Flag to indicate a new-iteration request is in flight to avoid race with mint
let pendingNewIter = false;

// User's Access Level, >= 3 is admin
let isLevel;

// Required information to make edits
let dbAestheticsObject;

// Redirect URL from query params - where to go when user clicks "Return"
let redirect;

// User authentication context from server (ID, permissions, decryption_success)
let user_context;

// Currently displayed iteration number (0, 1, 2, etc.)
// null = no entity loaded yet
let currentIter = null;

// Controls which side of the card is visible: 'main' (front) or other tools
// When switched, card_main is hidden and datasurface shows the tool view
var activeFace = 'main';

function collapseValue(n, length = 8) {
    return Math.floor((n - 1) / length);
}

/* Navigate to Entity : Build the URL component, execute on click */
function NavigateToEntity(ent, z) {
    const xyzi = encodeURIComponent(`${ent.positionX},${ent.positionY},${z},${ent.iter}`);
    const redirect = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `entity.html?xyzi=`+xyzi+`&redirect=${redirect}`;
}

/**
 * Continuously updates a timestamp element to show elapsed time since entity creation.
 * Uses requestAnimationFrame for smooth updates without blocking.
 * Format: Xd:Xh:Xm:Xs (days:hours:minutes:seconds)
 * @param {HTMLElement} e - Element with data-ts attribute (Unix timestamp in seconds)
 */
function updateTS(e) {
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
        e.innerHTML = `${days}d:${hours}h:${minutes}m:${seconds}s`;
    }

    requestAnimationFrame(() => updateTS(e));
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

function safeRedirect(path) {
    // Prevent open redirects by only allowing relative paths starting with /
    if (path && path.startsWith("/") && !path.startsWith("//")) {
        window.location.href = path;
    } else {
        window.location.href = "./index.html";
    }
};

function safeExit() {
    // Navigate back to redirect URL or default to index
    const params = new URLSearchParams(window.location.search);
    let redirectTo = params.get("redirect") || "./index.html";
    
    // Defensively decode if the value still appears to be encoded
    // (starts with % indicating URL-encoded characters)
    if (redirectTo && redirectTo.startsWith("%") && !redirectTo.startsWith("/")) {
        try {
            redirectTo = decodeURIComponent(redirectTo);
        } catch (e) {
            console.warn('Failed to decode redirect:', redirectTo);
        }
    }
    
    safeRedirect(redirectTo);
};

/**
 * Makes AJAX request to fetch entity data from the server.
 * Called on page load and when navigating between iterations.
 * 
 * @param {string} url - API endpoint (fe_server /api/render/one)
 * @param {number} x - X coordinate in the spatial map
 * @param {number} y - Y coordinate in the spatial map
 * @param {number} z - Zone ID (0-7, 8 total zones)
 * @param {number} i - Desired iteration number to display
 * @param {string} apikey - Optional API key for authenticated requests
 * @returns {Promise} jQuery AJAX promise
 */
function Factory(url, x, y, z, i, apikey=null) {
    return $.ajax({
        type: "POST",
        url: url,
        timeout: 1500,
        contentType: "application/json",
        dataType: "json",
        headers: apikey ? { "X-API-Key": apikey } : {},
        data: JSON.stringify({ 'x_pos': x, 'y_pos': y, 'zone': z, 'iter': i })
    })
}

/**
 * Make AJAX request to fetch ownership rows from the server.
 * This is used for the ownership section.
 * Zone is added to the URL, not the query.
 * 
 * @param {string} url 
 * @param {string} ownership_id 
 * @param {number} after_index 
 * @returns {Promise} jQuery AJAX promise
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


function shuffle(array) {
    // Fisher-Yates shuffle algorithm for randomizing color order
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

/**
 * Sets CSS variables for zone color palette.
 * Each zone has a unique set of colors (banner array) that define the visual theme.
 * These colors are applied to card animations and visual elements.
 * 
 * @param {Object} res - Server response containing banner color array
 */
function illuminate(res) {
    // Shuffle the color array to add visual variation
    b = shuffle(res.banner);
    b.forEach((value, i) => {
        document.documentElement.style.setProperty(`--banner-channel-${i}`, value);
    });
}

// ──── Card Flip Mechanism ────────────────────────────────────────────────────
// The entity card has two sides:
// - Front (card_main): Displays entity name, description, glyphs, timestamp
// - Back (datasurface): Dynamically populated with tool views (edit, history, etc)

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

/**
 * Swaps between card front (main entity view) and back (tool views).
 * Clears datasurface before switching to prepare for new tool content.
 * 
 * @param {string} active - Tool name: 'rm', 'edit', 'history', 'owner', etc
 */
function cardSwap(active) {
    // Remove any previous datasurface content to prevent stale data
    const d = document.getElementById('datasurface');
    d.innerHTML = '';

    const c = document.getElementById('card_main');
    if (active == activeFace) {
        // Same tool clicked again - toggle back to front
        if (c.style.display === 'none') {
            _toggle(true, 'card_main');
            _toggle(false, 'datasurface');
            _toggle(true, 'cellbar_top');
            _toggle(true, 'cellbar_bottom');
        } else {
            _toggle(false, 'card_main');
            _toggle(true, 'datasurface');
            _toggle(false, 'cellbar_top');
            _toggle(false, 'cellbar_bottom');
        }
    } else {
        // Different tool clicked - switch to new tool view
        _toggle(false, 'card_main');
        _toggle(true, 'datasurface');
        _toggle(false, 'cellbar_top');
        _toggle(false, 'cellbar_bottom');
        activeFace = active
    }
}

/**
 * Highlights the active tool button in the top toolbar.
 * Only shows highlight when datasurface (back side) is visible.
 * 
 * @param {string} nav_name - Tool button ID to highlight
 */
function underline_tool_nav(nav_name) {
    const navs = ['nav_tools_rm', 'nav_tools_edit', 'nav_tools_history', 'nav_tools_id'];
    const c = document.getElementById('card_main');
    if (c.style.display === 'none') {
        // Back side is showing - highlight the active tool
        for (const n in navs) {
            if (navs[n] === nav_name) {
                d = document.getElementById(nav_name);
                d.className = 'tools_selected'
            } else {
                d = document.getElementById(navs[n])
                d.className = ''
            }
        }
    } else {
        // Front side is showing - clear all highlights
        for (const n in navs) {
            d = document.getElementById(navs[n])
            d.className = ''
        }
    }
}

/**
 * Displays removal interface for the entity.
 * Genesis iteration (#0) cannot be removed (only minted).
 * Future/TODO: Only the latest iteration in the stack may be removed.
 */
function showCardRm() {
    cardSwap('rm');
    underline_tool_nav('nav_tools_rm');
    c = document.getElementById('card_main')
    if (c.style.display === 'block') {
        return
    }
    if (currentIter == 0) {
        // Genesis card - show prohibition message
        const char_quote = '<i class="ri-prohibited-line"></i> ';
        const char_quote_long = ' '+char_quote;
        var description = "Removal not allowed; Genesis #0 cannot be removed, only minted";
        while (description.replaceAll(char_quote_long, '').length < 1500) {
            description = description + char_quote_long + description;
        }
        description = char_quote + description;
        const ds = document.getElementById('datasurface');
        const specular_layer = document.createElement("div");
        specular_layer.className = 'card specular';
        specular_layer.style.setProperty('--spec-channel', '#3d3d3d');
        const content = document.createElement("div");
        content.className = "content";
        content.style.setProperty("word-break", "break-all");
        const description_layer = document.createElement("div");
        description_layer.innerHTML = description;

        content.appendChild(description_layer);
        specular_layer.appendChild(content);
        ds.appendChild(specular_layer);
    } // else if (currentIter+1 < entity.length)
    // as only the last card in the stack may be removed. TODO
}

/**
 * Displays edit interface for the entity.
 * TODO: Implement edit form (only available for unminted or owned entities)
 */
function showCardEdit() {
    cardSwap('edit');
    underline_tool_nav('nav_tools_edit');
    c = document.getElementById('card_main')
    if (c.style.display === 'block') {
        return
    }
    // Admins (isLevel >= 3) can edit anyway.
    if (entity[currentIter].ownership != user_context.ID && isLevel < 3) {
        const char_quote = '<i class="ri-prohibited-line"></i> ';
        const char_quote_long = ' '+char_quote;
        var description = "You don't have ownership.";
        while (description.replaceAll(char_quote_long, '').length < 1500) {
            description = description + char_quote_long + description;
        }
        description = char_quote + description;
        const ds = document.getElementById('datasurface');
        const specular_layer = document.createElement("div");
        specular_layer.className = 'card specular';
        specular_layer.style.setProperty('--spec-channel', '#5e5e5eff');
        const content = document.createElement("div");
        content.className = "content";
        content.style.setProperty("word-break", "break-all");
        const description_layer = document.createElement("div");
        description_layer.innerHTML = description;

        content.appendChild(description_layer);
        specular_layer.appendChild(content);
        ds.appendChild(specular_layer);
    } else if (entity[currentIter].minted && isLevel < 3) {
        const char_quote = '<i class="ri-prohibited-line"></i> ';
        const char_quote_long = ' '+char_quote;
        var description = "This iteration is minted, editing not allowed.";
        while (description.replaceAll(char_quote_long, '').length < 1500) {
            description = description + char_quote_long + description;
        }
        description = char_quote + description;
        const ds = document.getElementById('datasurface');
        const specular_layer = document.createElement("div");
        specular_layer.className = 'card specular';
        specular_layer.style.setProperty('--spec-channel', '#5e5e5eff');
        const content = document.createElement("div");
        content.className = "content";
        content.style.setProperty("word-break", "break-all");
        const description_layer = document.createElement("div");
        description_layer.innerHTML = description;

        content.appendChild(description_layer);
        specular_layer.appendChild(content);
        ds.appendChild(specular_layer);
    }
}


function renderFromHistorical(i) {
    currentIter = i;
    renderCurrentCard()
}

/**
 * Displays history of all entity iterations.
 * Shows version timeline and allows jumping between iterations.
 * TODO: Implement history view
 */
function showCardHistory() {
    cardSwap('history');
    underline_tool_nav('nav_tools_history');
    c = document.getElementById('card_main')
    if (c.style.display === 'block') {
        return
    }
    const ds = document.getElementById('datasurface');
    ds.style.setProperty('overflow-y', 'scroll');
    const specular_layer = document.createElement("div");
    const content = document.createElement("div");
    content.className = "content";
    content.style.setProperty("word-break", "break-all");
    const description_layer = document.createElement("div");
    description_layer.innerHTML = '';
    for (const i in entity) {
        let e = entity[i];
        
        // time
        const ts_area = document.createElement("div")
        ts_area.className = "ts holoshim";
        ts_area.style.setProperty("padding", "10px");
        ts_area.style.setProperty("width", "100%");

        ts_area.innerText = '--:--:--:-- #?';
        ts_area.dataset.ts = e.timestamp;
        const minted_icon = (e.minted) ? '<i class="ri-copper-coin-fill"></i>' : '<i class="ri-copper-coin-line"></i>';
        updateTS_descript(ts_area, minted_icon + ` #${e.iter} <i class="ri-time-line"></i>`);

        const linked_text = document.createElement("div");
        linked_text.appendChild(ts_area);

        linked_text.className = "linked_historical_text";
        const channels = Object.values(e.aesthetics.bar);
        linked_text.style.setProperty("--ch0", channels[7]);
        linked_text.style.setProperty("--ch1", channels[0]);

        //linked_text.innerHTML = e.name + '<br>';
        linked_text.onclick = () => renderFromHistorical(i);

        //linked_text.appendChild(ts_area)
        description_layer.appendChild(linked_text);

    }

    content.appendChild(description_layer);
    specular_layer.appendChild(content);
    ds.appendChild(specular_layer);
}

function applyDataStateChannel(pad, bar) {
    if (!bar || typeof bar !== "object") return;

    const channels = Object.values(bar);

    channels.forEach((c, i) => {
        pad.style.setProperty(`--dc${i}`, c);
    });
}

function applyChannelAnimation(pad, bar) {
    if (!bar || typeof bar !== "object") return;

    const channels = Object.values(bar); // channel_0 → channel_7

    channels.forEach((c, i) => {
        pad.style.setProperty(`--c${i}`, c);
    });

    // First 4 drive the background animation
    for (let i = 0; i < 4; i++) {
        pad.style.setProperty(`--ch-${i}`, channels[i % channels.length]);
    }
}

function renderOwnerEntities(res, z, container) {
    console.log(res);
    if (res?.rows) {

        // TODO : (Currently Unused)
        // If rows > 100, link should appear for next page
        // based on the cursor position.
        const hasMoreData = res.has_more;
        const next_cursor = res.next_cursor; // db cursor
        const total = res.total;

        res.rows.reverse().forEach(e => {
            let x_axis = collapseValue(e.positionX);
            let y_axis = collapseValue(e.positionY);
            let m  = (e.minted) ? '<i class="ri-copper-coin-fill"></i>' : '<i class="ri-copper-coin-line"></i>';
            const xyzi = `x${e.positionX}, y${e.positionY}, z${z}, ${m} #${e.iter} @ X${x_axis}, Y${y_axis}`;
            let this_cell_is_local_entity = (e.positionX == entity[currentIter].positionX && e.positionY == entity[currentIter].positionY) ? '<i class="ri-focus-2-fill"></i> ' : '';

            const cell = document.createElement("div");
            cell.className = "cell";
            cell.dataset.state = e.state ?? 0;
            
            applyDataStateChannel(cell, e.aesthetics?.bar);
            
            const pad = document.createElement("div");
            pad.className = "cell-pad";

            applyChannelAnimation(pad, e.aesthetics?.bar);
            
            const seed = parseInt(e.uuid?.replace(/-/g, "").slice(0, 6), 16) || 0;
            pad.style.animationDelay = `${-(seed % 1200) / 100}s`;


            const inner = document.createElement("div");
            inner.className = "cell-inner";

            const top = document.createElement("div");
            top.className = "glyph-top";

            const bottom = document.createElement("div");
            bottom.className = "glyph-bottom";

            const glyphs = Object.values(e.aesthetics?.glyphs || {});
            glyphs.slice(0, 8).forEach((g, i) => {
                const d = document.createElement("div");
                d.className = "glyph-slot";
                if (i == 7) {
                    d.style=("cursor: pointer");
                    d.className = "glyph-slot NavElement"
                    d.onclick = () => NavigateToEntity(e, z);
                }
                d.textContent = g;

                d.style.setProperty("--glyph-ch", i);
                d.style.animationDelay = `${i * 0.2}s`;

                if (i < 4) top.appendChild(d);
                else bottom.appendChild(d);
            });

            const center = document.createElement("div");
            center.className = "center extrusionbase";

            const uuid = document.createElement("div");
            uuid.className = "uuid";
            uuid.innerHTML = `${this_cell_is_local_entity}${e.uuid.slice(0, 8)} ${xyzi}`;


            const owner = document.createElement("div");
            owner.className = "owner";
            owner.textContent = (e.ownership ?? "00000000").split('-')[0];

            // extrusion tooltip with hidden timestamp
            const extrusion = document.createElement("div");
            extrusion.className = "extrude";

            // Hidden timestamp value in a data attribute
            const timestamp = e.timestamp ?? 0; // float/int
            extrusion.dataset.ts = timestamp;

            const display = document.createElement("div");
            display.textContent = "--:--:--:--";
            extrusion.appendChild(display);

            // Function to update the display
            function updateExtrusion() {
                const ts = parseFloat(extrusion.dataset.ts) * 1000;
                if (ts === 0) {
                    display.innerHTML = "--:--:--:--";
                } else {
                    let diff = (Date.now() - ts) / 1000; // seconds
                    const days = Math.floor(diff / 86400);
                    const hours = Math.floor((diff % 86400) / 3600);
                    const minutes = Math.floor((diff % 3600) / 60);
                    const seconds = Math.floor(diff % 60);
                    display.innerHTML = `${days}d${hours}h${minutes}m${seconds}s`;
                }
                requestAnimationFrame(updateExtrusion);
            }

            const channels = Object.values(e.aesthetics?.bar);
            const CellBar = document.createElement("div");
            CellBar.className = "cell-bar";

            channels.forEach((c, i) => {
                const next = channels[(i + 1) % channels.length];
                const BarEl = document.createElement("div");
                BarEl.style.setProperty(`--xch0`, c)
                BarEl.style.setProperty(`--xch1`, next)
                BarEl.className = "bar-el";
                CellBar.append(BarEl)
            })

            extrusion.append(CellBar);

            requestAnimationFrame(updateExtrusion);

            center.append(uuid, owner, extrusion);
            inner.append(top, center, bottom);
            pad.append(inner);
            cell.append(pad);

            container.appendChild(cell);
        })
        _toggle(false, 'loading');
    } else {
        _toggle(false, 'loading')
        launch_error_toast(res?.db_health?.message || "Unexpected error occurred.");
    }
}

/**
 * Displays ownership information and user permissions.
 * Shows who owns the entity and what actions are available.
 * NOTE : after_index should be built in renderOwnerEntities.
*/
function showCardOwner() {
    cardSwap('owner');
    underline_tool_nav('nav_tools_id');
    c = document.getElementById('card_main')
    if (c.style.display === 'block') {
        return
    }

    let e = entity[0];
    const z = e.positionZ;
    const entity_stack_owner = e.ownership;

    const ds = document.getElementById('datasurface');
    ds.style.setProperty('overflow-y', 'scroll');
    const specular_layer = document.createElement("div");
    const content = document.createElement("div");
    content.className = "content";
    content.style.setProperty("font-style", "monospace");
    const description_layer = document.createElement("div");
    description_layer.style.setProperty('padding', '10px');
    description_layer.innerHTML = '';

    // (Render Entity Info), z above
    const entity_card_layer = document.createElement("div");
    const l = Object.keys(entity).length - 1;
    let i  = entity[currentIter].iter;
    let o  = entity[currentIter].ownership || 'No ownership.';
    let ro = (entity[currentIter].ownership) ? '<i class="ri-passport-fill"></i> ' + o : '<i class="ri-passport-line"></i> No ownership.'
    let m  = (entity[currentIter].minted) ? '<i class="ri-copper-coin-fill"></i>' : '<i class="ri-copper-coin-line"></i>';
    let X  = entity[currentIter].positionX;
    let Y  = entity[currentIter].positionY;
    let u  = entity[currentIter].uuid;
    let s  = entity[currentIter].state;
    let ts = entity[currentIter].timestamp;
    const date = new Date(ts * 1000);
    const info_data = document.createElement("div");
    info_data.innerHTML = `${m} x${X}, y${Y}, z${z}, #${i}/${l}<br>${ro}<br><i class="ri-focus-2-fill"></i> ${u}<br><i class="ri-time-line"></i> ${date.toString()}<br><br>`;

    if (entity_stack_owner) {
        _toggle(true, 'loading')
        QueryOwnershipData('https://octo.shadowsword.ca/api/ownership', entity_stack_owner, z)
        .done(function (res) {
            renderOwnerEntities(res, z, description_layer);
        })
        .fail(function  () {
            QueryOwnershipData('http://localhost:9300/api/ownership', entity_stack_owner, z)
            .done(function (res) {
                renderOwnerEntities(res, z, description_layer);
            })
            .fail(function (dataOrJqXHR, textStatus, jqXHRorError) {
                // NOTE : This can be used for other failure returns.
                const jqXHR = dataOrJqXHR.status ? dataOrJqXHR : jqXHRorError;
                let status = jqXHR.status;
                launch_error_toast(`${textStatus}: ${status}`);
                _toggle(false, 'loading')
            })
        })
    }

    // render
    description_layer.appendChild(info_data);
    content.appendChild(description_layer); // append function data here
    specular_layer.appendChild(content);
    ds.appendChild(specular_layer);
}

/**
 * Toggles visibility of mint control menu on the card.
 * Minting options:
 * - Mint: Commit genesis (#0) to database (requires ownership)
 * - New: Create next iteration (#1, #2, etc) after genesis is minted
 * Uses event delegation for robustness across DOM re-renders.
 */
function showMintControl(event) {
    if (event && event.target) {
        // Called from event listener - find mint_ctrl within clicked element
        const mintShim = event.target.closest('.mintshim');
        if (mintShim) {
            const m = mintShim.querySelector('#mint_control');
            if (m) {
                m.style.display = (m.style.display === 'block') ? 'none' : 'block';
            }
        }
    } else {
        // Fallback for inline onclick (shouldn't happen with new approach)
        m = document.getElementById('mint_control');
        if (m) {
            m.style.display = (m.style.display === 'block') ? 'none' : 'block';
        }
    }
}

// ──── Navigation & URL Management ────────────────────────────────────────────

/**
 * Updates the user login/profile navigation based on authentication status.
 * Shows user ID if authenticated, login button if not.
 * 
 * @param {Object} res - Server response with user_context
 */
function ChangeUserNav(res) {
    nav = document.getElementById('user-login-nav');
    // Build redirect for user/login pages pointing back to current page
    const currentPageRedirect = encodeURIComponent(window.location.pathname + window.location.search);
    
    if (res.user_context.decryption_success) {
        // User authenticated - show their ID (first segment of UUID)
        nav.href = 'user.html?redirect=' + currentPageRedirect;
        nav.innerHTML = '<i class="ri-passport-fill"></i> ' + String(res.user_context.ID).split('-')[0];
    } else {
        // User not authenticated - show login button
        nav.href = `login.html?redirect=${currentPageRedirect}`;
    }
}

/**
 * Updates area navigation link to return to area view with current state.
 */
function ChangeAreaNav() {
    nav = document.getElementById('area-nav');
    // Build redirect for area page pointing back to current page
    const currentPageRedirect = encodeURIComponent(window.location.pathname + window.location.search);
    nav.href = 'area.html?redirect=' + currentPageRedirect;
}

/**
 * Updates browser URL without reloading page to reflect current entity location.
 * Preserves the existing redirect parameter from the global redirect variable.
 * Format: ?xyzi=x,y,z,iter&redirect=...
 * 
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @param {number} z - Zone ID
 * @param {number} i - Iteration number
 */
function normalizeURL(x,y,z,i) {
    const params = new URLSearchParams();
    params.set("xyzi", `${x},${y},${z},${i}`);
    
    // Preserve the redirect parameter from the global redirect variable (set at page load)
    if (redirect) {
        params.set("redirect", redirect);
    }

    const newURL = `${window.location.pathname}?${params.toString()}`;

    window.history.replaceState({}, "", newURL);
}

/**
 * Validates and converts a value to non-negative number.
 * Used for parsing URL coordinates and iteration numbers.
 * 
 * @param {*} value - Value to convert
 * @param {number} fallback - Default if conversion fails
 * @returns {number} Valid non-negative number or fallback
 */
function nonNegativeNumber(value, fallback) {
    const v = Number(value);
    return Number.isFinite(v) && v >= 0 ? v : fallback;
}

/**
 * Retrieves API key from browser cookies.
 * API key authenticates requests to protected endpoints.
 * 
 * @returns {string|null} API key or null if not found
 */
function getApiKeyFromCookie() {
    const match = document.cookie.match(/(?:^|; )X-API-Key=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : null;
}


function launch_toast(normal_text) {
    var t = document.getElementById("normal_toast")
    var d = document.getElementById("normal_desc")
    t.className = "show";
    d.innerText = normal_text;
    setTimeout(function(){ t.className = t.className.replace("show", ""); }, 5000);
};

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
 * Applies zone color palette to card element for CSS animations.
 * Each entity has 8 color channels (from aesthetics.bar) that drive visual effects.
 * Channels 0-3 are used for background animations, all 8 for full palette.
 * 
 * @param {HTMLElement} pad - Element to apply colors to
 * @param {Object} bar - Color channel object {channel_0: '#...', ...}
 */
function applyChannelAnimation(pad, bar) {
    if (!bar || typeof bar !== "object") return;

    const channels = Object.values(bar); // channel_0 → channel_7

    channels.forEach((c, i) => {
        pad.style.setProperty(`--c${i}`, c);
    });

    // Primary animation colors (uses first 4 channels)
    for (let i = 0; i < 4; i++) {
        pad.style.setProperty(`--ch-${i}`, channels[i % channels.length]);
    }
}

function handleMint(res) {
    _toggle(false, 'loading');
    console.log(res);
    if (res?.entity) {
        entity = res.entity;
        
        // Update user context if provided
        if (res.user_context) {
            user_context = res.user_context;
        }
        
        // Re-render the card with updated state
        renderCurrentCard();
        launch_toast('Entity minted successfully!');
    } else {
        console.warn('Server did not respond with entity.');
        launch_error_toast(res?.db_health?.message || "Unexpected error occurred.");
    }
}

function mintRequest() {
    if (pendingNewIter) {
        launch_error_toast('Please wait for new iteration to finish.');
        return;
    }
    _toggle(true, 'loading')
    const e = entity[currentIter];
    const apiKey = getApiKeyFromCookie();
    Factory("https://octo.shadowsword.ca/api/mint", e.positionX, e.positionY, e.positionZ, currentIter, apiKey)
    .done(function (res) {
        handleMint(res)
    })
    .fail(function () {
        Factory("http://localhost:9300/api/mint", e.positionX, e.positionY, e.positionZ, currentIter, apiKey)
        .done(function (res) {
            handleMint(res)
        })
        .fail(function () {
            _toggle(false, 'loading')
            launch_error_toast('No server reachable.')
            console.warn('Server Com Failure')
        })
    })
}

function handleNewIter(res) {
    _toggle(false, 'loading');
    // Clear pending flag regardless of outcome
    pendingNewIter = false;
    if (res?.entity) {
        // res.entity is a mapping of iteration -> entity data
        entity = res.entity;

        // Update user context if provided
        if (res.user_context) {
            user_context = res.user_context;
        }

        // Get the latest iteration key and set currentIter
        const lastKey = Math.max(...Object.keys(res.entity).map(Number));
        currentIter = Number(lastKey);

        renderCurrentCard();
        launch_toast("New Iteration Generation Success")
    } else {
        console.warn('Server did not respond with entity.');
        pendingNewIter = false;
        launch_error_toast(res?.db_health?.message || "Unexpected error occurred.");
    }
}

function iterRequest() {
    // Prevent duplicate requests
    if (pendingNewIter) {
        launch_error_toast('New iteration already in progress.');
        return;
    }

    const prevIter = Number(currentIter);
    const e = entity[prevIter]
    const nextIter = Number(prevIter) + 1;

    // Create optimistic placeholder for the new iteration
    try {
        const placeholder = JSON.parse(JSON.stringify(e));
        placeholder.iter = nextIter;
        placeholder.minted = false;
        placeholder.exists = false;
        placeholder.name = placeholder.name ? placeholder.name + ' (pending)' : 'New (pending)';
        placeholder.state = 2;
        // Remove index so DB will generate one on commit
        delete placeholder.index;

        entity[nextIter] = placeholder;
        currentIter = nextIter;
        renderCurrentCard();
    } catch (err) {
        console.warn('Failed to create optimistic placeholder', err);
    }

    // Mark that a new-iteration is pending to prevent users from minting the wrong iter
    pendingNewIter = true;
    _toggle(true, 'loading')
    const apiKey = getApiKeyFromCookie();
    Factory("https://octo.shadowsword.ca/api/newiter", e.positionX, e.positionY, e.positionZ, e.iter, apiKey)
    .done(function (res) {
        console.log(res);
        handleNewIter(res);
    })
    .fail(function () {
        Factory("http://localhost:9300/api/newiter", e.positionX, e.positionY, e.positionZ, e.iter, apiKey)
        .done(function (res) {
            console.log(res);
            handleNewIter(res);
        })
        .fail(function () {
            _toggle(false, 'loading')
            // Clear pending flag on failure and revert optimistic placeholder
            pendingNewIter = false;
            // Remove optimistic placeholder if present
            try {
                if (entity && entity[prevIter + 1] && entity[prevIter + 1].exists === false) {
                    delete entity[prevIter + 1];
                }
            } catch (err) {
                console.warn('Failed to remove optimistic placeholder', err);
            }
            // Restore previous iteration
            currentIter = prevIter;
            renderCurrentCard();
            launch_error_toast('Something went wrong.')
            console.warn('Server Com Failure')
        })
    })

}

/**
 * Dynamically constructs the complete card DOM element from entity data.
 * Handles:
 * - Entity content (name, description, glyphs, timestamp)
 * - Tool buttons and navigation
 * - Color animations and visual styling
 * - Mint control for genesis cards
 * 
 * @param {Object} entity_data - Single iteration of entity from server
 * @param {number} key - Iteration number (0, 1, 2, etc)
 * @returns {HTMLElement} Complete card wrapper ready to insert into DOM
 */
function buildCard(entity_data, key) {
    // Pad description with decorative quotes to reach ~1500 chars
    // This creates a visually full card face
    const char_quote = '<i class="ri-chat-quote-line"></i> ';
    const char_quote_long = ' '+char_quote;
    var description = entity_data.description;
    while (description.replaceAll(char_quote_long, '').length < 1500) {
        description = description + char_quote_long + description;
    }
    description = char_quote + description;

    // wrapper setup
    const wrapper = document.createElement("div");
    wrapper.className = "cardWrapper";
    wrapper.id = "entity_"+entity_data.iter;

    // tools setup
    const tools = document.createElement("div");
    tools.className = "tools holoshim";
    
    const tools_rm = document.createElement("a")
    tools_rm.id = 'nav_tools_rm'
    tools_rm.innerHTML = '<span onclick="showCardRm()"><i class="ri-file-shred-fill"></i> rm</span>'

    const tools_edit = document.createElement("a")
    tools_edit.id = 'nav_tools_edit'
    tools_edit.innerHTML = '<span onclick="showCardEdit()"><i class="ri-pencil-ai-fill"></i> edit</span>'

    const tools_history = document.createElement("a");
    tools_history.id = 'nav_tools_history'
    tools_history.innerHTML = '<span onclick="showCardHistory()"><i class="ri-time-line"></i> history</span>'

    const tools_user = document.createElement("a");
    const ownership = entity_data.ownership ?? '00000000';
    tools_user.id = 'nav_tools_id'
    tools_user.style.setProperty('font-family', 'monospace');
    tools_user.innerHTML = `<span onclick="showCardOwner()"><i class="ri-user-fill"></i> ${ownership.split('-')[0]}</span>`;

    // card setup
    // Card front (main entity view)
    const card = document.createElement("div");
    card.className = "card specular";
    card.id = "card_main";

    // Card back (tool views - edit, history, owner, remove)
    const data_surface = document.createElement("div");
    data_surface.className = "card";
    data_surface.style.setProperty("display", "none"); // Hidden until tool clicked
    data_surface.id = "datasurface";
    
    // Extract zone color palette and apply primary color (channel 7 = darkest/primary)
    const bar_colors = entity_data.aesthetics?.bar;
    const channels = Object.values(bar_colors);
    card.style.setProperty("--spec-channel", channels[7]);
    // TODO: Use darkened version of primary color for better contrast
    
    const iter_number = document.createElement("div");
    iter_number.className = "iter-number";
    iter_number.innerText = '#' + key ?? '0';

    const cellbar_top = document.createElement("div");
    cellbar_top.id = "cellbar_top";
    cellbar_top.className = "cell-bar";
    cellbar_top.style.setProperty('position', 'absolute');
    cellbar_top.style.setProperty('top', '260px');

    const cellbar_bottom = document.createElement("div");
    cellbar_bottom.id = "cellbar_bottom";
    cellbar_bottom.className = "cell-bar";
    cellbar_bottom.style.setProperty('position', 'absolute');
    cellbar_bottom.style.setProperty('top', '525px');

    const base_layer = document.createElement("div");
    base_layer.className = "content";
    base_layer.style.setProperty("word-break", "break-all");

    const description_layer = document.createElement("div");
    description_layer.innerHTML = description;

    const central_element = document.createElement("div");
    central_element.className ="cardCenter";
    const ts_area = document.createElement("div")
    ts_area.className = "ts";
    // For now we'll leave the timestamp default blank, animate later
    ts_area.innerText = '--:--:--:--';
    ts_area.dataset.ts = entity_data.timestamp;

    updateTS(ts_area);

    // Card's db entity UUID
    const card_id = document.createElement("div");
    card_id.className = "cardID";
    const id_actual = document.createElement("span");
    id_actual.innerHTML = '<i class="ri-focus-2-line"></i>' + entity_data.uuid;

    // Glyphs & Minted Indicator
    const glyph_elements = document.createElement("div");
    const top = document.createElement("div");
    top.className = "glyph-top topElements";
    const bottom = document.createElement("div");
    bottom.className = "glyph-bottom bottomElements";

    // Mint indicator (coin icon) - shows whether entity has been committed to DB
    const mint_shim = document.createElement("div");
    mint_shim.className = "glyph-slot holoshim mintshim";
    mint_shim.style.setProperty("font-size", "30px");
    mint_shim.id = 'mint_shim';
    //mint_shim.setAttribute('data-mint-trigger', 'true'); // Mark for event delegation
    if ((entity_data.minted == true) && (entity_data.exists == true) ) {
        mint_shim.innerHTML = '<i class="ri-copper-coin-fill"></i>'; // Filled = minted
    } else {
        mint_shim.innerHTML = '<i class="ri-copper-coin-line"></i>' // Outline = not minted
    }
    mint_shim.style.setProperty("--from", "#fff")
    mint_shim.style.setProperty("--to", "#8e8e8e")
    mint_shim.onclick = () => showMintControl()

    // Mint control menu (appears when coin is clicked)
    // TODO: Implement actual mint and create new iteration functionality
    const mint_ctrl = document.createElement("div");
    mint_ctrl.className = 'extrude';
    mint_ctrl.id = 'mint_control';
    
    const user_could_be_owner = ((entity_data.ownership ?? user_context.ID) == user_context.ID);
    const user_is_owner = (entity_data.ownership == user_context.ID)
    
    // Extract user permission level from encrypted token
    const level = user_context.data
        .find(v => typeof v === 'string' && v.startsWith('isLevel'))
        ?.match(/\d+/)?.[0];
    isLevel = level ? Number(level) : 0 ;

    console.log(`DEBUG: owner: ${user_could_be_owner} (Decrypted: ${user_context.decryption_success}), minted: ${entity_data.minted}, level: ${isLevel}, iter: ${currentIter} & ${entity_data.iter}, total_iterations: ${Object.keys(entity).length}`);
    
    // Mint conditions:
    // 1. User must be the owner
    // 2. Entity must NOT be minted yet (iteration #0 only)
    // 3. User must be authenticated (decryption_success)
    const mint_request_ctrl = (user_could_be_owner && (entity_data.minted == false) && user_context.decryption_success) ? '<a onclick="mintRequest()"><i class="ri-copper-coin-fill"></i> Mint</a> ' : ''
    const new_entity_ctrl = (user_is_owner) ? '<a onclick="iterRequest()"><i class="ri-function-add-line"></i> New</a>' : ''
    if ((mint_request_ctrl == '') && (new_entity_ctrl == '')) {
        mint_ctrl.innerHTML = '<i class="ri-prohibited-line"></i>'
    } else {
        mint_ctrl.innerHTML = '<i class="ri-alert-line"></i> ' + mint_request_ctrl + new_entity_ctrl
    }
    mint_shim.append(mint_ctrl);
    
    const glyphs = Object.values(entity_data.aesthetics?.glyphs || {});
    glyphs.slice(0, 8).forEach((g, i) => {
        const d = document.createElement("div");
        d.className = "glyph-slot glyph-actual";
        d.textContent = g;

        d.style.setProperty("--glyph-ch", i);

        const next = channels[(i + 1) % channels.length];
        d.style.setProperty("--from", channels[i])
        d.style.setProperty("--to", next)

        d.style.animationDelay = `${i * 0.2}s`;
        
        if (i < 4) top.appendChild(d);
        else bottom.appendChild(d);
    })

    channels.forEach((c, i) => {
        const ch = document.createElement("div");
        const next = channels[(i + 1) % channels.length];
        ch.style.setProperty('--xch0', c);
        ch.style.setProperty('--xch1', next);
        ch.className = 'ent-el';
        if (i < 4) {
            cellbar_top.appendChild(ch)
        } else {
            cellbar_bottom.appendChild(ch)
        }  
    })

    applyChannelAnimation(glyph_elements, entity_data.aesthetics?.bar);

    // assembly
    
    top.appendChild(mint_shim);
    glyph_elements.append(top, bottom);

    tools.append(tools_rm, ' | ', tools_edit, ' | ', tools_history, ' | ', tools_user, iter_number);
    wrapper.append(tools);

    central_element.append(entity_data.name, ts_area)
    card_id.append(id_actual);
    base_layer.append(description_layer, card_id);
    card.append(base_layer, central_element, glyph_elements);
    wrapper.append(data_surface, card, cellbar_top, cellbar_bottom);

    return wrapper;
}

// ──── Content Loading & Rendering ────────────────────────────────────────────

/**
 * Initializes page state from server response.
 * Stores entity version history and sets up display.
 * 
 * @param {Object} res - Server response {entity: {0: {...}, 1: {...}}, intended_iter: 0}
 */
function populateContainer(res) {
    // Store all iterations of the entity (version history)
    entity = res.entity;

    // Set current display to the intended iteration (usually latest)
    const intended_iter = Number(res.intended_iter);
    currentIter = Number.isFinite(intended_iter) ? intended_iter : null;

    container.innerHTML = '';
    renderCurrentCard();
}

/**
 * Renders the currently selected iteration into the page.
 * Fetches entity data at currentIter and builds the card DOM.
 */
function renderCurrentCard() {
    if (!entity || currentIter === null) {
        launch_error_toast('No entity loaded.');
        return;
    }

    const data = entity[currentIter];
    if (data) {
        container.innerHTML = '';
        const card = buildCard(data, currentIter);
        container.appendChild(card);
        
        // Update URL bar to reflect current location (don't include redirect to prevent nesting)
        normalizeURL(data.positionX, data.positionY, data.positionZ, data.iter)
    } else {
        launch_error_toast('No card available for this iteration.');
    }
}

/**
 * Processes successful API response and renders the entity.
 * Handles authentication state, user nav, and page styling.
 * 
 * @param {Object} res - Complete server response with entity, user_context, banner
 */
function handleSuccess(res) {
    console.log(res);
    if (res?.entity) {
        // Update global state
        user_context = res.user_context;
        ChangeUserNav(res);
        populateContainer(res);
        illuminate(res);
        _toggle(false, 'loading');
        _toggle(false, 'skeletonloading');
    } else {
        console.warn('Server did not respond with entity.')
        launch_error_toast(res?.db_health?.message || "Unexpected error occurred.")
    }
}

// ──── Page Initialization ────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", function () {
    // Retrieve API key for authenticated requests
    const apiKey = getApiKeyFromCookie();
    
    // ──── Iteration Navigation Handlers ─────────────────────────────────────
    // "Back" button: Jump to previous iteration (if exists)
    const backBtn = document.getElementById('x_minus');
    const nextBtn = document.getElementById('x_plus');

    if (backBtn) {
        backBtn.addEventListener('click', function (ev) {
            ev.preventDefault();
            if (!entity || currentIter === null) return launch_error_toast('No entity loaded.');
            const prev = Number(currentIter) - 1;
            if (prev >= 0 && entity[prev]) {
                currentIter = prev;
                renderCurrentCard();
            } else {
                launch_error_toast('No previous card available.');
            }
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', function (ev) {
            ev.preventDefault();
            if (!entity || currentIter === null) return launch_error_toast('No entity loaded.');
            const nxt = Number(currentIter) + 1;
            if (entity[nxt]) {
                currentIter = nxt;
                renderCurrentCard();
            } else {
                launch_error_toast('No next card available.');
            }
        });
    }
    
    // ──── Parse URL Parameters ──────────────────────────────────────────────
    // Expected format: ?xyzi=x,y,z,iter&redirect=url
    const params = new URLSearchParams(window.location.search);
    const xyzi = (params.get('xyzi') ?? '0,0,0,0').split(',');
    redirect = params.get('redirect'); // Store in global for later use
    
    // Extract coordinates (validate as non-negative integers)
    const xpos = Math.floor(nonNegativeNumber(xyzi[0] ?? 0, 0));
    const ypos = Math.floor(nonNegativeNumber(xyzi[1] ?? 0, 0));
    // Enforce [0,1,2,3,4,5,6,7] # 8 Zones
    const zone = Math.min(number_of_zones-1, Math.max(0, Math.floor(nonNegativeNumber(xyzi[2] ?? 0, 0))));
    
    // Iteration to display
    const ITER = Math.floor(nonNegativeNumber(xyzi[3] ?? 0, 0));

    // Normalize URL with validated parameters (redirect preserved from global variable)
    normalizeURL(xpos, ypos, zone, ITER);
    ChangeAreaNav();

    // ──── Fetch Entity Data ─────────────────────────────────────────────────
    // Try production server first, fallback to localhost for development
    Factory("https://octo.shadowsword.ca/api/render/one", xpos, ypos, zone, ITER, apiKey)
    .done(function (res) {
        handleSuccess(res);
    })
    .fail(function () {
        // Production failed - try local dev server
        Factory("http://localhost:9300/api/render/one", xpos, ypos, zone, ITER, apiKey)
        .done(function (res) {
            handleSuccess(res);
        })
        .fail(function () {
            launch_error_toast('No server reachable.');
            console.warn('Server Com Failure');
        });
    });
});
