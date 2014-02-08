(function(d, s, id) {
  var js, fjs = d.getElementsByTagName(s)[0];
  if (d.getElementById(id)) return;
  js = d.createElement(s); js.id = id;
  js.src = "//connect.facebook.net/en_US/all.js#xfbml=1&appId=151899248267008";
  fjs.parentNode.insertBefore(js, fjs);
}(document, 'script', 'facebook-jssdk'));

(function() {
  var script = document.createElement('script'); script.type = 'text/javascript'; script.async = true;
  script.src = '//apis.google.com/js/plusone.js';
  var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(script, s);
})();

(function(){
  var twitterWidgets = document.createElement('script');
  twitterWidgets.type = 'text/javascript';
  twitterWidgets.async = true;
  twitterWidgets.src = '//platform.twitter.com/widgets.js';
  document.getElementsByTagName('head')[0].appendChild(twitterWidgets);
})();
