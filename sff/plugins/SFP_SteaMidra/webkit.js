function injectSteaMidraButton() {
    if (document.getElementById('steamidra-btn')) return;

    function getSteamAppId() {
        const match = window.location.pathname.match(/^\/app\/(\d+)/);
        return match ? match[1] : null;
    }

    const appId = getSteamAppId();
    if (!appId) return;

    // Red debug button
    const debugBtn = document.createElement("button");
    debugBtn.id = "steamidra-debug";
    debugBtn.innerText = "SteaMidra JS Injected (SFP)";
    debugBtn.style.position = "fixed";
    debugBtn.style.bottom = "20px";
    debugBtn.style.right = "20px";
    debugBtn.style.zIndex = "999999";
    debugBtn.style.padding = "10px";
    debugBtn.style.backgroundColor = "green";
    debugBtn.style.color = "white";
    document.body.appendChild(debugBtn);

    // Target the right column on the store page where purchase options are
    const rightCol = document.querySelector('.game_area_purchase_game_wrapper') || document.querySelector('.apphub_OtherSiteInfo');
    if (rightCol) {
        const btnContainer = document.createElement('div');
        btnContainer.className = 'game_area_purchase_game';
        btnContainer.style.backgroundColor = '#1a9fff';
        btnContainer.style.marginBottom = '15px';
        btnContainer.style.padding = '10px';
        btnContainer.style.borderRadius = '3px';
        btnContainer.style.cursor = 'pointer';

        const btnText = document.createElement('h1');
        btnText.innerText = 'Add to SteaMidra Library';
        btnText.style.color = 'white';
        btnText.style.fontSize = '18px';
        btnText.style.margin = '0';
        btnText.style.textAlign = 'center';

        btnContainer.appendChild(btnText);
        btnContainer.id = 'steamidra-btn';

        btnContainer.onclick = function(e) {
            e.preventDefault();
            window.location.href = "midra://add/" + appId;
        };

        rightCol.parentNode.insertBefore(btnContainer, rightCol);
    }
}

// Observe DOM mutations to inject the button dynamically as the page loads
const observer = new MutationObserver((mutations) => {
    if (window.location.href.includes('/app/')) {
        injectSteaMidraButton();
    }
});

observer.observe(document.body, { childList: true, subtree: true });

// Initial check
if (window.location.href.includes('/app/')) {
    injectSteaMidraButton();
}
