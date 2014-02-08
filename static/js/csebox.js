  google.load('search', '1', {language : 'en', style : google.loader.themes.V2_DEFAULT});
  google.setOnLoadCallback(function() {
    var customSearchOptions = {};
    var orderByOptions = {};
    orderByOptions['keys'] = [{label: 'Relevance', key: ''},{label: 'Date', key: 'date'}];
    customSearchOptions['enableOrderBy'] = true;
    customSearchOptions['orderByOptions'] = orderByOptions;  var customSearchControl = new google.search.CustomSearchControl(
      '004224684705477634910:-lggz-loulo', customSearchOptions);
    customSearchControl.setResultSetSize(google.search.Search.FILTERED_CSE_RESULTSET);
    var options = new google.search.DrawOptions();
    options.setAutoComplete(true);
    customSearchControl.setAutoCompletionId('004224684705477634910:-lggz-loulo+qptype:1');
    options.enableSearchboxOnly("/search/");
    customSearchControl.draw('cse-search-form', options);
  }, true);
