const launcher = require("./main_ui_node_desktop.js");


if (require.main === module && typeof launcher.main === "function") {
  launcher.main();
}


module.exports = launcher;
