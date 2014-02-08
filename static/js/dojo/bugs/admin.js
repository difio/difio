require(["dojo"]);
require(["dojo/dom"]);
require(["dojo/cookie"]);

function delete_bug(advId, bugNum, postUrl){
var li = dojo.byId("bug"+bugNum);
var xhrArgs = { url: postUrl,
content: {bug: bugNum, advisory: advId},
preventCache: true, headers: {"X-CSRFToken":dojo.cookie("csrftoken")},
load: function(data){ li.style.display="none";},
error: function(error){ li.style.background="red";}
}; var deferred = dojo.xhrPost(xhrArgs);}
