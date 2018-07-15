// script from https://github.com/aio-libs/aiohttp/blob/master/examples/websocket.html
// This invokes this code when the page is ready
$(function () {
    var conn = null;

    function log(msg) {
        var control = $('#log');
        control.html(control.html() + msg + '<br/>');
        control.scrollTop(control.scrollTop() + 1000);
    }

    function connect() {
        disconnect();
        var wsUri = (window.location.protocol == 'https:' && 'wss://' || 'ws://') + window.location.host + '/ws';
        conn = new WebSocket(wsUri);
        log('Connecting...');
        conn.onopen = function () {
            log('Connected.');
            update_ui();
        };
        conn.onmessage = function (e) {
            //log('Received: ' + e.data);
            let json_data = JSON.parse(e.data);
            update_bus_arrivals(json_data);
            update_last_updated();
        };
        conn.onclose = function () {
            log('Disconnected.');
            conn = null;
            update_ui();
        };
    }

    function disconnect() {
        if (conn != null) {
            log('Disconnecting...');
            conn.close();
            conn = null;
            update_ui();
        }
    }

    function update_last_updated() {
        let now = new Date();
        $('#last_updated').text("Last updated: " + now);
    }

    function update_bus_arrivals(json_data) {

        let rows = '';
        Object.keys(json_data).forEach(function (key, index) {
            rows = rows + "<tr><td class='h2'>" + key + "</td></tr>";
            for (t in  json_data[key]) {
                rows = rows + "<tr><td class='h3'>" + json_data[key][t] + "</td></tr>";
            }

        });
        let arrivals_html = "<table class='table'>" + rows + "</table>";
        $('#arrivals').html(arrivals_html);

    }

    function update_ui() {
        if (conn == null) {
            $('#status').text('disconnected');
            $('#connect').html('Connect');
        } else {
            $('#status').text('connected (' + conn.protocol + ')');
            $('#connect').html('Disconnect');
        }
    }


    $('#connect').click(function () {
        if (conn == null) {
            connect();
        } else {
            disconnect();
        }
        update_ui();
        return false;
    });

    // connect on page load
    connect();
    update_ui();

});
