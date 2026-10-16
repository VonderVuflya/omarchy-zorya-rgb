import QtQuick
import qs.Ui as Ui

Ui.BarWidget {
    id: widget
    moduleName: "vondervuflya.zorya-rgb"
    readonly property Panel panel: popup.item as Panel
    readonly property bool opened: widget.panel ? widget.panel.opened : false
    readonly property bool popoutSwitchClosing: widget.panel ? widget.panel.popoutSwitchClosing : false
    function open() { if (widget.panel) widget.panel.open() }
    function close() { if (widget.panel) widget.panel.close() }
    function closeForPopoutSwitch() { if (widget.panel) widget.panel.closeForPopoutSwitch() }
    function togglePanel() { if (opened) close(); else open() }
    function inject() {
        if (!widget.panel) return
        widget.panel.bar = widget.bar
        widget.panel.settings = widget.settings
        widget.panel.anchorItem = button
        widget.panel.hostWidget = widget
    }
    onBarChanged: inject()
    onSettingsChanged: inject()
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    Loader {
        id: popup
        source: Qt.resolvedUrl("Panel.qml")
        visible: false
        onLoaded: { widget.inject(); Qt.callLater(widget.inject) }
    }
    Ui.BarIconButton {
        id: button
        anchors.fill: parent
        bar: widget.bar
        text: widget.panel && widget.panel.backend.updateAvailable ? "↑" : "\udb80\udd2b"
        tooltipText: widget.panel && widget.panel.backend.updateAvailable
            ? "ZoryaRGB · Update to " + widget.panel.backend.updateInfo.latest_version : "ZoryaRGB"
        onPressed: function(mouseButton) { if (mouseButton === Qt.LeftButton) widget.togglePanel() }
    }
}
