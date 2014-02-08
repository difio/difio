function uuid() {
    require(["dojo/io-query"], function (ioQuery) {
        var uri = window.location.toString();

        var end = uri.indexOf("#");
        if (end < 0) { end = uri.length; }

        var query = uri.substring(uri.indexOf("?") + 1, end);
        var queryObject = ioQuery.queryToObject(query);

        if (queryObject['uuid'] === undefined ) {
            return
        }

        for (i=0; i < document.links.length; i++) {
            if(/\?/.test(document.links[i].href) && (! /\#/.test(document.links[i].href))){
                document.links[i].href += "uuid=";
                document.links[i].href += queryObject['uuid'];
            }
        }
    });
}
