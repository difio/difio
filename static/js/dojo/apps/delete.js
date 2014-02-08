require(["dojo"]);
require(["dojo/dom"]);
require(["dojo/cookie"]);

function deleteInstalledPackage(instId, postUrl){
var tableRow = dojo.byId("i"+instId);
var xhrArgs = { url: postUrl,
content: {user: dojo.byId("userId").innerHTML,
installed: instId},
preventCache: true, headers: {"X-CSRFToken":dojo.cookie("csrftoken")},
load: function(data){ tableRow.style.display="none";},
error: function(error){ tableRow.style.background="red";}
}; var deferred = dojo.xhrPost(xhrArgs);}

function deleteApplication(appId, postUrl){
var tableRow = dojo.byId("a"+appId);
var xhrArgs = { url: postUrl,
content: {user: dojo.byId("userId").innerHTML, app: appId},
preventCache: true, headers: {"X-CSRFToken":dojo.cookie("csrftoken")},
load: function(data){ tableRow.style.display="none";},
error: function(error){ tableRow.style.background="red";}
}; var deferred = dojo.xhrPost(xhrArgs);}
