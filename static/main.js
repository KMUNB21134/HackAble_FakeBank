function initRecipientCheck() {
    var btn = document.getElementById('check-recipient-btn');
    var input = document.getElementById('recipient');
    var status = document.getElementById('recipient-status');
    if (!btn || !input || !status) {
        return;
    }

    btn.addEventListener('click', function () {
        var username = input.value.trim();
        if (!username) {
            return;
        }
        status.textContent = 'Checking...';
        fetch('/check-recipient?username=' + encodeURIComponent(username))
            .then(function (res) { return res.json(); })
            .then(function (data) {
                status.textContent = data.exists
                    ? 'Recipient found: ' + data.match
                    : 'No account with that username.';
            })
            .catch(function () {
                status.textContent = 'Could not check recipient right now.';
            });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRecipientCheck);
} else {
    initRecipientCheck();
}
