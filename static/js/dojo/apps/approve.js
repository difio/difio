require(["dojo"]);
require(["dojo/dom"]);
require(["dojo/cookie"]);

function approveApplication(appId, postUrl){
var tableRow = dojo.byId("a"+appId);
var xhrArgs = { url: postUrl,
content: {user: dojo.byId("userId").innerHTML, app: appId},
preventCache: true, headers: {"X-CSRFToken":dojo.cookie("csrftoken")},
load: function(data){ window.location.href = "/applications/" + appId + "/";},
error: function(error){ tableRow.style.background="red";}
}; var deferred = dojo.xhrPost(xhrArgs);}
