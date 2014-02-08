require(["dojo"]);
require(["dijit"]);

function sendForm(){
    var form = dojo.byId("inviteForm");
    dojo.connect(form, "onsubmit", function(event){
        dojo.stopEvent(event);
        var xhrArgs = {
            form: dojo.byId("inviteForm"),
            handleAs: "text",
            load: function(data){
                dijit.byId("inviteFriends").hide();
            },
            error: function(error){
                dijit.byId("inviteFriends").hide();
                alert('ERROR! Please file a bug report! Thanks!');
            }
        }
        var deferred = dojo.xhrPost(xhrArgs);
    });
}
dojo.ready(sendForm);
