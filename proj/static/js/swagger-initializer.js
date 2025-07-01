window.onload = function() {
  //<editor-fold desc="Changeable Configuration Block">

  // Custom plugin to hide the API definition URL
  const HideInfoUrlPartsPlugin = () => {
    return {
      wrapComponents: {
        InfoUrl: () => () => null
      }
    }
  }

  window.ui = SwaggerUIBundle({
    url: document.getElementById("swagger-ui").getAttribute('openapi-url'),
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [
      SwaggerUIBundle.presets.apis//,
      //SwaggerUIStandalonePreset
    ],
    plugins: [
      HideInfoUrlPartsPlugin
    ],
    // layout: "StandaloneLayout"
  });

  //</editor-fold>
};
