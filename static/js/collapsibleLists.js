//CONFIGURATION

// images are defined in the calling page to avoid hard-coding the absolute URL
// collapsedImage='/static/v18/i/li/plus.jpg';
// expandedImage='/static/v18/i/li/minus.jpg';

defaultState=0; //1 = show, 0 = hide
/* makeCollapsible - makes a list have collapsible sublists
 * 
 * listElement - the element representing the list to make collapsible
 */
function makeCollapsible(listElement,listState){
  if(listState!=null) defaultState=listState;

  // removed list item bullets and the sapce they occupy
  listElement.style.listStyle='none';
  listElement.style.marginLeft='0';
  listElement.style.paddingLeft='0';

  // loop over all child elements of the list
  var child=listElement.firstChild;
  while (child!=null){

    // only process li elements (and not text elements)
    if (child.nodeType==1){

      // build a list of child ol and ul elements and show/hide them
      var list=new Array();
      var grandchild=child.firstChild;
      while (grandchild!=null){
        if (grandchild.tagName=='OL' || grandchild.tagName=='UL'){
          if(defaultState==1) grandchild.style.display='block';
		  else grandchild.style.display='none';
          list.push(grandchild);
        }
        grandchild=grandchild.nextSibling;
      }

      // add toggle buttons
	  if(defaultState==1) {
		  var node=document.createElement('img');
		  node.setAttribute('src',expandedImage);
		  node.setAttribute('class','collapsibleOpen');
		  node.style.marginRight="5px";
		  node.style.display = "inline";
		  node.onclick=createToggleFunction(node,list);
		  child.insertBefore(node,child.firstChild);
	  } else {
		  var node=document.createElement('img');
		  node.setAttribute('src',collapsedImage);
		  node.setAttribute('class','collapsibleClosed');
		  node.style.marginRight="5px";
		  node.style.display = "inline";
		  node.onclick=createToggleFunction(node,list);
		  child.insertBefore(node,child.firstChild);
	  }
    }

    child=child.nextSibling;
  }

}

/* createToggleFunction - returns a function that toggles the sublist display
 * 
 * toggleElement  - the element representing the toggle gadget
 * sublistElement - an array of elements representing the sublists that should
 *                  be opened or closed when the toggle gadget is clicked
 */
function createToggleFunction(toggleElement,sublistElements){

  return function(){

    // toggle status of toggle gadget
    if (toggleElement.getAttribute('class')=='collapsibleClosed'){
      toggleElement.setAttribute('class','collapsibleOpen');
      toggleElement.setAttribute('src',expandedImage);
    }else{
      toggleElement.setAttribute('class','collapsibleClosed');
      toggleElement.setAttribute('src',collapsedImage);
    }

    // toggle display of sublists
    for (var i=0;i<sublistElements.length;i++){
      sublistElements[i].style.display=
          (sublistElements[i].style.display=='block')?'none':'block';
    }

  }

}
