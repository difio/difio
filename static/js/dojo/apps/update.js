require(["dojo/dom"]);
require(["dojo/cookie"]);
require(["dijit/InlineEditBox"]);
require(["dijit/form/TextBox"]);

function updateAppName(postUrl, imgUrl){
var statusImg = dojo.byId("nameStatus");
var xhrArgs = { url: postUrl,
content: {user: dojo.byId("userId").innerHTML,
app: dojo.byId("appId").innerHTML, name: dijit.byId("appName").get("value")},
preventCache: true, headers: {"X-CSRFToken":dojo.cookie("csrftoken")},
load: function(data){ statusImg.src = imgUrl+"ok.png";},
error: function(error){ statusImg.src = imgUrl+"error.png";}
}; var deferred = dojo.xhrPost(xhrArgs);}

function updateAppUrl(postUrl, imgUrl){
var statusImg = dojo.byId("urlStatus");
var xhrArgs = { url: postUrl,
content: {user: dojo.byId("userId").innerHTML,
app: dojo.byId("appId").innerHTML, url: dijit.byId("appUrl").get("value")},
preventCache: true, headers: {"X-CSRFToken":dojo.cookie("csrftoken")},
load: function(data){ statusImg.src = imgUrl+"ok.png";},
error: function(error){ statusImg.src = imgUrl+"error.png";}
}; var deferred = dojo.xhrPost(xhrArgs);}
