
// ============================================================================
// OCTO ENTITY VIEWER - Frontend Display Logic
// ============================================================================
// This page displays a single "Entity" which is a versioned object stored in
// a spatial database. Entities exist at coordinates (x, y, zone) and can have
// multiple iterations/versions. Iteration #0 is the genesis version that must
// be minted (committed to DB) before additional iterations can be created.
// ============================================================================

// ──── Global State Variables ────────────────────────────────────────────────
const container = document.getElementById('container');

// Entity versioning system: { 0: genesis_entity, 1: updated_entity, ... }
// Keys are iteration numbers, values are entity data objects from the server
var entity;

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
    const encodedRedirect = params.get("redirect");
    // Decode the redirect parameter if it exists
    const redirectTo = encodedRedirect ? decodeURIComponent(encodedRedirect) : "./index.html";
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
        } else {
            _toggle(false, 'card_main');
            _toggle(true, 'datasurface');
        }
    } else {
        // Different tool clicked - switch to new tool view
        _toggle(false, 'card_main');
        _toggle(true, 'datasurface');
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
}

/**
 * Displays history of all entity iterations.
 * Shows version timeline and allows jumping between iterations.
 * TODO: Implement history view
 */
function showCardHistory() {
    cardSwap('history');
    underline_tool_nav('nav_tools_history');
}

/**
 * Displays ownership information and user permissions.
 * Shows who owns the entity and what actions are available.
 * TODO: Implement owner view
 */
function showCardOwner() {
    cardSwap('owner');
    underline_tool_nav('nav_tools_id');
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
    if (res.user_context.decryption_success) {
        // User authenticated - show their ID (first segment of UUID)
        redirect = encodeURIComponent(window.location.pathname + window.location.search);
        nav.href = 'user.html?redirect=' + redirect; // This will point to the user page
        nav.innerHTML = '<i class="ri-passport-fill"></i> ' + String(res.user_context.ID).split('-')[0];
    } else {
        // User not authenticated - show login button
        nav.href = `login.html?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`;
    }
}

/**
 * Updates area navigation link to return to area view with current state.
 */
function ChangeAreaNav() {
    nav = document.getElementById('area-nav');
    redirect = encodeURIComponent(window.location.pathname + window.location.search);
    nav.href = 'area.html?redirect=' + redirect;
}

/**
 * Updates browser URL without reloading page to reflect current entity location.
 * Format: ?xyzi=x,y,z,iter&redirect=url
 * 
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @param {number} z - Zone ID
 * @param {number} i - Iteration number
 * @param {string} redirect - Return URL for navigation
 */
function normalizeURL(x,y,z,i,redirect) {
    const params = new URLSearchParams();

    params.set("xyzi", x+','+y+','+z+','+i);
    params.set("redirect", redirect)

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
        
        // Update mint icon to show filled coin (minted state)
        const mint_element = document.querySelector('.mintshim');
        if (mint_element && entity[currentIter].minted === true) {
            mint_element.innerHTML = '<i class="ri-copper-coin-fill"></i>';
        }
        
        launch_toast('Entity minted successfully!');
    } else {
        console.warn('Server did not respond with entity.');
        launch_error_toast(res?.db_health?.message || "Unexpected error occurred.");
    }
}

function mintRequest() {
    _toggle(true, 'loading')
    const e = entity[currentIter]
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
    cellbar_top.className = "cell-bar";
    cellbar_top.style.setProperty('position', 'absolute');
    cellbar_top.style.setProperty('top', '260px');

    const cellbar_bottom = document.createElement("div");
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
    mint_shim.setAttribute('data-mint-trigger', 'true'); // Mark for event delegation
    if ((entity_data.minted == true) && (entity_data.exists == true) ) {
        mint_shim.innerHTML = '<i class="ri-copper-coin-fill"></i>'; // Filled = minted
    } else {
        mint_shim.innerHTML = '<i class="ri-copper-coin-line"></i>' // Outline = not minted
    }
    mint_shim.style.setProperty("--from", "#fff")
    mint_shim.style.setProperty("--to", "#8e8e8e")

    // Mint control menu (appears when coin is clicked)
    // TODO: Implement actual mint and create new iteration functionality
    const mint_ctrl = document.createElement("div");
    mint_ctrl.className = 'extrude';
    mint_ctrl.id = 'mint_control';
    
    const user_is_owner = ((entity_data.ownership ?? user_context.ID) == user_context.ID);
    
    // Extract user permission level from encrypted token
    const level = user_context.data
        .find(v => typeof v === 'string' && v.startsWith('isLevel'))
        ?.match(/\d+/)?.[0];
    const isLevel = level ? Number(level) : 0 ;

    console.log(`DEBUG: owner: ${user_is_owner} (Decrypted: ${user_context.decryption_success}), minted: ${entity_data.minted}, level: ${isLevel}, iter: ${currentIter} & ${entity_data.iter}, total_iterations: ${Object.keys(entity).length}`);
    
    // Mint conditions:
    // 1. User must be the owner
    // 2. Entity must NOT be minted yet (iteration #0 only)
    // 3. User must be authenticated (decryption_success)
    const mint_request_ctrl = (user_is_owner && (entity_data.minted == false) && user_context.decryption_success) ? '<a onclick="mintRequest()"><i class="ri-copper-coin-fill"></i> Mint</a> ' : ''
    mint_ctrl.innerHTML = '<i class="ri-alert-line"></i> ' + mint_request_ctrl + '<a><i class="ri-function-add-line"></i> New</a>'
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
        
        // Add event delegation for mint_shim clicks
        const mintShim = container.querySelector('[data-mint-trigger="true"]');
        if (mintShim) {
            mintShim.addEventListener('click', showMintControl);
        }
        
        // Update URL bar to reflect current location
        normalizeURL(data.positionX, data.positionY, data.positionZ, data.iter, redirect ?? 'area.html')
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
    redirect = params.get('redirect');
    
    // Extract coordinates (validate as non-negative integers)
    const xpos = Math.floor(nonNegativeNumber(xyzi[0] ?? 0, 0));
    const ypos = Math.floor(nonNegativeNumber(xyzi[1] ?? 0, 0));
    // Enforce [0,1,2,3,4,5,6,7] # 8 Zones
    const zone = Math.min(7, Math.max(0, Math.floor(nonNegativeNumber(xyzi[2] ?? 0, 0))));
    
    // Iteration to display
    const ITER = Math.floor(nonNegativeNumber(xyzi[3] ?? 0, 0));

    // Normalize URL with validated parameters
    normalizeURL(xpos, ypos, zone, ITER, redirect ?? 'area.html');
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
