require(["dojo"]);
require(["dijit"]);

function sendReminderForm(){
    var form = dojo.byId("reminderForm");

    dojo.connect(form, "onsubmit", function(event){
        dojo.stopEvent(event);
        dijit.byId("dlgForgot").hide();
        var xhrArgs = {
            form: form,
            handleAs: "text",
            load: function(data){alert(data);},
            error: function(error, ioargs){alert(ioargs.xhr.responseText);}
        }; var deferred = dojo.xhrPost(xhrArgs);
    });
}
dojo.ready(sendReminderForm);
