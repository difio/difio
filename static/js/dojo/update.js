require(["dojo"]);
require(["dojo/dom"]);
// custom string functions
String.prototype.startsWith = function(str) {return (this.match("^"+str)==str)}

function hideLoading(content, loading) {
content.style.display = 'block';
loading.style.display = 'none';
}

function toggleVisibility(first, second) {
var first = document.getElementById(first);
var second = document.getElementById(second);
if (second.style.display == 'none') {
    showLoading(first, second);
} else {
    hideLoading(first, second);
}
}

function showLoading(content, loading) {
content.style.display = 'none';
loading.style.display = 'block';
}

var localCache = {};

function load_data(fieldURL, timeStamp, pre, hl, baseURL) {
var loadingGif = document.getElementById('jsonLoading');
var contentHolder = document.getElementById('jsonContent');

if (localCache.hasOwnProperty(fieldURL)) {
    contentHolder.innerHTML = localCache[fieldURL];
    hideLoading(contentHolder, loadingGif);
} else {
    showLoading(contentHolder, loadingGif);
    var xhrArgs = {
        url: fieldURL,
        handleAs: "json",
        content: {t: timeStamp},
        headers: {"Content-Type": "application/json"},
        load: function(jsonData, ioargs){
            if (baseURL) {
                content = display_private_content(baseURL, jsonData, contentHolder, loadingGif);
            } else {
                content = display_public_content(jsonData, contentHolder, loadingGif, hl, pre);
            }
            localCache[fieldURL] = content;
        },
        error: function(error, ioargs) {
            if ((ioargs.xhr.status == 403) || (ioargs.xhr.status == 404)) {
                // older analytics just don't have this
                display_public_content("We're sorry! This information is not available.", contentHolder, loadingGif, true, true);
            } else {
                contentHolder.innerHTML = error + " " + ioargs.xhr.status + " : " + ioargs.xhr.responseText + "<br />We're using CORS! Does your browser <a href='http://caniuse.com/cors'>support it</a>?";
            }
            hideLoading(contentHolder, loadingGif);
        }
    };
    if (timeStamp == null) {
        xhrArgs['content'] = null;
    }
    var deferred = dojo.xhrGet(xhrArgs);
}
if (hl) { hljs.highlightBlock(contentHolder, null); }
}

function display_public_content(content, contentHolder, loadingGif, hl, pre){
    if (hl) { content = "<code class='brush: diff'>"+content+"</code>"; }
    if (pre) { content = "<pre>"+content+"</pre>"; }
    contentHolder.innerHTML = content;
    hideLoading(contentHolder, loadingGif);
    if (hl) { hljs.highlightBlock(contentHolder, null); }

    return content;
}

function display_private_content(baseURL, content, contentHolder, loadingGif){
    var diff_ids = new Array();

    var text = "";
    text += "<table style='width:100%'>";
    for (var i=0; i<content['tests'].length; i++) {
        var test = content['tests'][i];
        var td = content[test];
        var is_diff = td['t'].startsWith('diff');
        var texta = td['t'].split('\n');

        var id_f = i+"first";
        var id_s = i+'second';

        text += "<tr><th";
        if (texta.length > 1) {
            text += ' onclick="toggleVisibility(\''+ id_f + '\', \'' + id_s + '\')"';
            text += " class='collapsible_results ";
        } else {
            text += " class='";
        }
        text += "vertical "+td['s']+" test_name" +"'>"+test+"</th>";
        text += "<td class='dots'>";

        var test_result = "";
        if (texta.length > 1) {
            test_result = '<pre id="'+id_f+'">' + texta[0] + '</pre>';
            test_result += '<pre id="'+id_s+'" style="display:none;">';
            if (is_diff) { test_result += "<code class='brush: diff'>"; diff_ids.push(id_s);}
            test_result += td['t'];
            if (is_diff) { test_result += "</code>"; }
            test_result += '</pre>';
        } else {
            test_result = "<pre>" + td['t'] + "</pre>";
            if (td['u']) {
                var now = moment().format('YYYYMMDDHHmmss');
                test_result = '<a href="#" onclick="load_data(\'' + baseURL + td['u'] +
                              '\', '+now+' , true, true);">' + test_result + '</a>';
            }
        }

        text += test_result;
        text += "</td></tr>";
    }

    text += "</table>";

    contentHolder.innerHTML = text;
    hideLoading(contentHolder, loadingGif);

    for (var i=0; i<diff_ids.length; i++) {
        var element = document.getElementById(diff_ids[i]);
        hljs.highlightBlock(element, null);
    }

    return text;
}
