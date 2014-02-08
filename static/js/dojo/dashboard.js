require(["dojo"]);
require(["dojo/dom"]);

function hideLoading(content, loading) {
    content.style.display = 'block';
    loading.style.display = 'none';
}

function showLoading(content, loading, hideContent) {
    if (hideContent == true){
        content.style.display = 'none';
    }
    loading.style.display = 'block';
}

function hideMoreBtn(more){
    more.style.display = 'none';
    more.style.visibility = 'hidden';
}

function display_packages(item, container){
    var text = '<div class="package dots">' +
                '<div class="container">' +
                '  <img src="' + item['img']  + '" alt="' + item['t'] + '" title="' + item['t'] + '" />' +
                '  <div class="name">' + item['n'] + '</div>';
    text += '  <div class="url"><a href="' + item['w'] + '">' + item['w'] + '</a></div>' +
            '  <div class="url"><a href="' + item['i'] + '">' + item['i'] + '</a></div>' +
            '</div>'; // end of container

    text += '<div id="versions'+item['pk']+'" class="versions">';
    for (var i=0; i<item['vsort'].length; i++) {
        var ver_pk = item['vsort'][i];
        var ver = item['v'][ver_pk];

        if (ver['f'] > 0) {
            text += "<span class='button micro following green' title='unfollow'" +
                    " id='v" + ver_pk + "'>" + ver['v'] + "</span> ";
        }

        if (ver['f'] == 0) {
            text += "<span class='button micro follow dark_border' title='follow'" +
                    " id='v" + ver_pk + "'>" + ver['v'] + "</span> ";
        }

        if (ver['f'] == -1) {
            text += "<span class='micro dark_border gray in_app' title='used in app' id='v" + ver_pk + "'>" + ver['v'] + "</span> ";
        }
    }
    text += '</div>'; // end of versions

    text += '</div>';
    container.innerHTML += text;
}


function sendSearchForm(){
    var stream = dojo.byId("stream");
    var loading = dojo.byId('loading');
    var more = dojo.byId("more");

    var form = dojo.byId("searchForm");

    dojo.connect(form, "onsubmit", function(event){
        dojo.stopEvent(event);

        showLoading(stream, loading, true);

        var xhrArgs = {
            form: form,
            preventCache : true,
            handleAs: "json",
            load: function(data){
                stream.innerHTML = "";
                showLoading(stream, loading, true);
                hideMoreBtn(more);

                if (data.length == 0) {
                    stream.innerHTML = "<h2>No packages found, matching your search! Try again!</h2>";
                }

                // loading stream record
                for (var i=0; i<data.length; i++) {
                    display_packages(data[i], stream);
                }

                hideLoading(stream, loading);
            },
            error: function(error){
                hideLoading(stream, loading);
                hideMoreBtn(more);
                alert('ERROR! Please file a bug report! Thanks!');
            }
        }
        var deferred = dojo.xhrPost(xhrArgs);
    });
}
dojo.ready(sendSearchForm);
