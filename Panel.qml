pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons as Commons
import qs.Ui as Ui
import "ColorModel.js" as Colors

Ui.Panel {
    id: root
    moduleName: "vondervuflya.zorya-rgb"
    manageIpc: false
    property var anchorItem: null
    property var hostWidget: null
    readonly property var barIdentity: hostWidget || root
    readonly property color foreground: Commons.Color.foreground
    // The shell exposes surface groups as dynamically populated QtObjects.
    // qmllint disable missing-property
    readonly property color themeSurface: Commons.Color.popups.background
    // qmllint enable missing-property
    readonly property color surface: Qt.rgba(themeSurface.r, themeSurface.g, themeSurface.b, 1)
    function controlFill(amount) {
        return Qt.rgba(surface.r + (foreground.r - surface.r) * amount,
                       surface.g + (foreground.g - surface.g) * amount,
                       surface.b + (foreground.b - surface.b) * amount, 1)
    }
    property string inputError: ""
    property Service backend: Service { active: root.opened }
    readonly property string selectedColor: root.backend.state.color || "#FFFFFF"
    readonly property var rgb: Colors.rgb(selectedColor)
    readonly property var hsv: Colors.hsv(selectedColor)
    readonly property var selectedIds: Array.isArray(root.backend.state.devices) ? root.backend.state.devices : []
    readonly property var presets: Array.isArray(root.backend.state.presets) ? root.backend.state.presets : []
    readonly property var unboundWireless: root.backend.diagnostics && Array.isArray(root.backend.diagnostics.wireless_devices)
        ? root.backend.diagnostics.wireless_devices.filter(function(device) { return device.is_unbound_wireless === true }) : []
    property int page: 0

    function open() { root.controller.show(); root.backend.refresh() }
    function close() { root.controller.hide() }
    // Omarchy injects a capability facade; navigation is an optional dynamic API.
    // qmllint disable missing-property
    function switchPanel(direction) {
        return root.bar && typeof root.bar.switchPanelFrom === "function"
            ? root.bar.switchPanelFrom(root.barIdentity, direction) : false
    }
    // qmllint enable missing-property
    function chooseColor(value) {
        var normalized = Colors.normalizeHex(value)
        if (!normalized) { inputError = "Enter a six-digit color, such as #A78BFA."; return }
        inputError = ""
        root.backend.update({color: normalized})
    }
    function toggleDevice(id, selected) {
        var ids = root.selectedIds.filter(function(candidate) { return candidate !== id })
        if (selected) ids.push(id)
        root.backend.update({devices: ids})
    }
    function presetAction(verb) {
        var preset = root.presets[presetPicker.currentIndex]
        if (preset) root.backend.command(["preset", verb, String(preset.id)])
    }
    function setup(component) { root.backend.command(["setup", "--component", component], "setup") }

    component RoundedButton: Button {
        id: buttonControl
        hoverEnabled: true
        background: Rectangle {
            implicitWidth: 80; implicitHeight: 28
            radius: 8
            color: root.controlFill(buttonControl.down ? 0.22 : buttonControl.hovered ? 0.14 : 0.08)
            border.width: 1
            border.color: buttonControl.visualFocus ? Commons.Color.accent : root.controlFill(buttonControl.hovered ? 0.28 : 0.16)
            opacity: buttonControl.enabled ? 1 : 0.6
            Behavior on color { ColorAnimation { duration: 90 } }
        }
    }

    component RoundedTabButton: TabButton {
        id: tabControl
        hoverEnabled: true
        background: Rectangle {
            implicitHeight: 25
            radius: 8
            color: root.controlFill(tabControl.down ? 0.24 : tabControl.checked ? 0.18 : tabControl.hovered ? 0.1 : 0.035)
            border.width: 1
            border.color: tabControl.visualFocus ? Commons.Color.accent : root.controlFill(tabControl.checked ? 0.28 : 0.06)
            Behavior on color { ColorAnimation { duration: 90 } }
        }
    }

    component RoundedComboBox: ComboBox {
        id: comboControl
        hoverEnabled: true
        background: Rectangle {
            implicitWidth: 120; implicitHeight: 28
            radius: 8
            color: root.controlFill(comboControl.down ? 0.2 : comboControl.hovered ? 0.12 : 0.07)
            border.width: 1
            border.color: comboControl.visualFocus ? Commons.Color.accent : root.controlFill(0.2)
            opacity: comboControl.enabled ? 1 : 0.6
            Behavior on color { ColorAnimation { duration: 90 } }
        }
    }

    component RoundedTextField: TextField {
        id: fieldControl
        background: Rectangle {
            implicitWidth: 120; implicitHeight: 28
            radius: 8
            color: root.controlFill(0.045)
            border.width: 1
            border.color: fieldControl.activeFocus ? Commons.Color.accent : root.controlFill(0.16)
        }
    }

    component RoundedSpinBox: SpinBox {
        id: spinControl
        background: Rectangle {
            implicitWidth: 70; implicitHeight: 28
            radius: 8
            color: root.controlFill(0.045)
            border.width: 1
            border.color: spinControl.activeFocus ? Commons.Color.accent : root.controlFill(0.16)
        }
        up.indicator: Rectangle {
            x: spinControl.width - width
            implicitWidth: 20; implicitHeight: 14
            width: 20; height: spinControl.height / 2
            radius: 6
            color: root.controlFill(spinControl.up.pressed ? 0.22 : spinControl.up.hovered ? 0.15 : 0.08)
            Text { anchors.centerIn: parent; text: "▴"; color: spinControl.palette.text; font.pixelSize: 11 }
        }
        down.indicator: Rectangle {
            x: spinControl.width - width
            y: spinControl.height - height
            implicitWidth: 20; implicitHeight: 14
            width: 20; height: spinControl.height / 2
            radius: 6
            color: root.controlFill(spinControl.down.pressed ? 0.22 : spinControl.down.hovered ? 0.15 : 0.08)
            Text { anchors.centerIn: parent; text: "▾"; color: spinControl.palette.text; font.pixelSize: 11 }
        }
    }

    Ui.KeyboardPanel {
        id: card
        anchorItem: root.anchorItem
        owner: root.barIdentity
        bar: root.bar
        open: root.opened
        centerOnBar: false
        contentWidth: card.fittedContentWidth(480)
        contentHeight: card.fittedContentHeight(620)
        focusTarget: content

        Pane {
            id: content
            anchors.fill: parent
            padding: 0
            focus: true
            // Fusion paints its gradients using several palette roles. All
            // surfaces must be opaque so they cannot blend with a light default.
            palette.window: root.surface
            palette.windowText: root.foreground
            palette.text: root.foreground
            palette.buttonText: root.foreground
            palette.base: root.controlFill(0.04)
            palette.alternateBase: root.controlFill(0.08)
            palette.button: root.controlFill(0.1)
            palette.light: root.controlFill(0.22)
            palette.midlight: root.controlFill(0.16)
            palette.mid: root.controlFill(0.08)
            palette.dark: root.surface
            palette.shadow: root.surface
            palette.placeholderText: root.controlFill(0.65)
            palette.disabled.windowText: root.controlFill(0.5)
            palette.disabled.text: root.controlFill(0.5)
            palette.disabled.buttonText: root.controlFill(0.5)
            palette.highlight: Commons.Color.accent
            palette.highlightedText: Commons.Color.accent.r * 0.2126 + Commons.Color.accent.g * 0.7152 + Commons.Color.accent.b * 0.0722 > 0.5 ? "#10131A" : "#FFFFFF"
            background: Item {}
            Keys.onEscapePressed: root.close()

            ColumnLayout {
                anchors.fill: parent
                spacing: 12
                RowLayout {
                    Layout.fillWidth: true
                    Rectangle { implicitWidth: 12; implicitHeight: 30; radius: 6; color: root.selectedColor }
                    ColumnLayout {
                        spacing: 0
                        Label { text: "ZORYA"; font.pixelSize: 22; font.bold: true; font.letterSpacing: 3 }
                        Label {
                            text: root.backend.busy ? "Applying · " + root.backend.operation
                                : root.backend.state.applying ? "Applying lighting…"
                                : root.backend.state.connected ? "Connected · " + (root.backend.state.device_count || root.backend.devices.length) + " devices"
                                : "Backend disconnected"
                            font.pixelSize: 11; opacity: 0.68
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Switch {
                        text: "Lights"
                        checked: root.backend.state.on === true
                        onToggled: root.backend.update({on: checked})
                    }
                    RoundedButton {
                        Layout.preferredWidth: 32
                        Layout.maximumWidth: 32
                        text: "×"
                        Accessible.name: "Close Zorya"
                        onClicked: root.close()
                    }
                }
                Rectangle {
                    visible: root.backend.error !== "" || root.inputError !== ""
                    Layout.fillWidth: true
                    implicitHeight: notice.implicitHeight + 16
                    radius: 8
                    color: Qt.rgba(1, 0.45, 0.3, 0.12)
                    Label {
                        id: notice
                        anchors.fill: parent; anchors.margins: 8
                        text: root.inputError || root.backend.error
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        font.pixelSize: 12
                    }
                }
                TabBar {
                    spacing: 4
                    padding: 3
                    background: Rectangle { radius: 10; color: root.controlFill(0.035) }
                    Layout.fillWidth: true
                    currentIndex: root.page
                    onCurrentIndexChanged: root.page = currentIndex
                    RoundedTabButton { text: "Color & effects" }
                    RoundedTabButton { text: "Devices" }
                    RoundedTabButton { text: "Setup" }
                }
                ScrollView {
                    id: scroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth

                    ColumnLayout {
                        width: scroll.availableWidth
                        spacing: 14
                        ColumnLayout {
                            visible: root.page === 0
                            Layout.fillWidth: true
                            spacing: 12
                            RowLayout {
                                Layout.fillWidth: true
                                ColorWheel {
                                    Layout.preferredWidth: 224
                                    Layout.preferredHeight: 224
                                    selectedColor: root.selectedColor
                                    onColorPicked: function(value) { root.chooseColor(value) }
                                    onInteractionFinished: root.backend.commitPending()
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: "COLOR"; font.pixelSize: 11; opacity: 0.65; font.letterSpacing: 2 }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 50
                                        radius: 8; color: root.selectedColor
                                        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.18)
                                    }
                                    RoundedTextField {
                                        id: hexInput
                                        Layout.fillWidth: true
                                        text: root.selectedColor
                                        maximumLength: 7
                                        selectByMouse: true
                                        font.family: "monospace"
                                        Accessible.name: "Primary HEX color"
                                        onEditingFinished: root.chooseColor(text)
                                    }
                                    RoundedButton {
                                        Layout.fillWidth: true
                                        text: "Pure white"
                                        onClicked: root.chooseColor("#FFFFFF")
                                    }
                                    Label { text: "Drag to blend hue and saturation.\nArrow keys work on the wheel."; wrapMode: Text.Wrap; font.pixelSize: 10; opacity: 0.65 }
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Repeater {
                                    model: ["R", "G", "B"]
                                    RowLayout {
                                        id: channelRow
                                        required property string modelData
                                        required property int index
                                        Layout.fillWidth: true
                                        Label { text: channelRow.modelData; opacity: 0.65 }
                                        RoundedSpinBox {
                                            Layout.fillWidth: true
                                            from: 0; to: 255; editable: true
                                            value: root.rgb[channelRow.index]
                                            Accessible.name: channelRow.modelData + " color channel"
                                            onValueModified: {
                                                var channels = root.rgb.slice()
                                                channels[channelRow.index] = value
                                                root.chooseColor(Colors.fromRgb(channels[0], channels[1], channels[2]))
                                            }
                                        }
                                    }
                                }
                            }
                            RowLayout {
                                Label { text: "Saturation"; Layout.preferredWidth: 84 }
                                Slider {
                                    Layout.fillWidth: true
                                    from: 0; to: 1; value: root.hsv.s
                                    Accessible.name: "Saturation"
                                    onMoved: root.chooseColor(Colors.fromHsv(root.hsv.h, value, root.hsv.v))
                                }
                                Label { text: Math.round(root.hsv.s * 100) + "%"; Layout.preferredWidth: 38; horizontalAlignment: Text.AlignRight }
                            }
                            RowLayout {
                                Label { text: "Brightness"; Layout.preferredWidth: 84 }
                                Slider {
                                    Layout.fillWidth: true
                                    from: 0; to: 100; stepSize: 1; value: root.backend.state.brightness
                                    Accessible.name: "Brightness"
                                    onMoved: root.backend.update({brightness: Math.round(value)})
                                }
                                Label { text: root.backend.state.brightness + "%"; Layout.preferredWidth: 38; horizontalAlignment: Text.AlignRight }
                            }
                            RowLayout {
                                Label { text: "Effect"; Layout.preferredWidth: 84 }
                                RoundedComboBox {
                                    id: effects
                                    Layout.fillWidth: true
                                    model: ["static", "pulse", "rainbow", "gradient"]
                                    currentIndex: Math.max(0, model.indexOf(root.backend.state.effect))
                                    Accessible.name: "Lighting effect"
                                    onActivated: root.backend.update({effect: model[currentIndex]})
                                }
                            }
                            RowLayout {
                                visible: root.backend.state.effect !== "static"
                                Label { text: "Speed"; Layout.preferredWidth: 84 }
                                Slider {
                                    Layout.fillWidth: true
                                    from: 0.1; to: 5; stepSize: 0.1; value: root.backend.state.speed
                                    Accessible.name: "Effect speed"
                                    onMoved: root.backend.update({speed: Math.round(value * 10) / 10})
                                }
                                Label { text: Number(root.backend.state.speed).toFixed(1) + "×"; Layout.preferredWidth: 38 }
                            }
                            RowLayout {
                                visible: root.backend.state.effect === "gradient"
                                Label { text: "Second color"; Layout.preferredWidth: 84 }
                                Rectangle { implicitWidth: 26; implicitHeight: 26; radius: 6; color: root.backend.state.secondary_color }
                                RoundedTextField {
                                    Layout.fillWidth: true
                                    text: root.backend.state.secondary_color
                                    maximumLength: 7
                                    Accessible.name: "Gradient second HEX color"
                                    onEditingFinished: {
                                        var value = Colors.normalizeHex(text)
                                        if (value) { root.inputError = ""; root.backend.update({secondary_color: value}) }
                                        else root.inputError = "Enter a six-digit second color, such as #8A6CFF."
                                    }
                                }
                            }
                            Label { text: "SAVED SCENES"; font.pixelSize: 11; font.letterSpacing: 2; opacity: 0.65 }
                            RowLayout {
                                Layout.fillWidth: true
                                RoundedTextField { id: presetName; Layout.fillWidth: true; placeholderText: "Scene name"; maximumLength: 64; Accessible.name: "Scene name" }
                                RoundedButton {
                                    text: "Save"
                                    enabled: presetName.text.trim() !== "" && !root.backend.busy
                                    onClicked: root.backend.command(["preset", "save", presetName.text.trim()])
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                RoundedComboBox {
                                    id: presetPicker
                                    Layout.fillWidth: true
                                    model: root.presets
                                    textRole: "name"
                                    enabled: root.presets.length > 0
                                    displayText: root.presets.length ? currentText : "No saved scenes"
                                    Accessible.name: "Saved scenes"
                                    onActivated: presetName.text = root.presets[currentIndex].name
                                }
                                RoundedButton { text: "Apply"; enabled: root.presets.length > 0 && !root.backend.busy; onClicked: root.presetAction("apply") }
                                RoundedButton { text: "Delete"; enabled: root.presets.length > 0 && !root.backend.busy; onClicked: root.presetAction("delete") }
                            }
                            Label { text: "Save again with the same name to update a scene."; font.pixelSize: 11; opacity: 0.65; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        }
                        ColumnLayout {
                            visible: root.page === 1
                            Layout.fillWidth: true
                            spacing: 12
                            RowLayout {
                                Layout.fillWidth: true
                                Label { text: root.selectedIds.length + " selected"; Layout.fillWidth: true }
                                RoundedButton {
                                    text: "All"
                                    enabled: root.backend.devices.length > 0
                                    onClicked: root.backend.update({devices: root.backend.devices.map(function(device) { return device.id })})
                                }
                                RoundedButton { text: "None"; enabled: root.selectedIds.length > 0; onClicked: root.backend.update({devices: []}) }
                                RoundedButton { text: "Refresh"; enabled: !root.backend.busy; onClicked: root.backend.refresh() }
                            }
                            Label { text: "Choose exactly which devices receive this scene. No devices are selected automatically."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12; opacity: 0.65 }
                            Repeater {
                                model: root.backend.devices
                                Rectangle {
                                    id: deviceCard
                                    required property var modelData
                                    Layout.fillWidth: true
                                    implicitHeight: deviceRow.implicitHeight + 16
                                    radius: 8
                                    color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
                                    RowLayout {
                                        id: deviceRow
                                        anchors.fill: parent; anchors.margins: 8
                                        CheckBox {
                                            checked: root.selectedIds.indexOf(deviceCard.modelData.id) !== -1
                                            Accessible.name: "Select " + deviceCard.modelData.name
                                            onToggled: root.toggleDevice(deviceCard.modelData.id, checked)
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            Label { text: deviceCard.modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                                            Label {
                                                text: deviceCard.modelData.led_count + " LEDs · " + deviceCard.modelData.location
                                                Layout.fillWidth: true; elide: Text.ElideRight; font.pixelSize: 10; opacity: 0.6
                                            }
                                        }
                                    }
                                }
                            }
                            Label { visible: !root.backend.devices.length; text: "No devices discovered. Check your backend and permissions in Setup."; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        }
                        ColumnLayout {
                            visible: root.page === 2
                            Layout.fillWidth: true
                            spacing: 12
                            Label { text: "HARDWARE & CONNECTION"; font.letterSpacing: 2; font.pixelSize: 11; opacity: 0.65 }
                            Label { text: "Inspect the connection before installing a component. Setup may ask for system authorization and a source build can take several minutes."; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
                            RoundedButton { text: "Run diagnostics"; enabled: !root.backend.busy; onClicked: root.backend.command(["doctor"], "doctor") }
                            Label {
                                visible: root.unboundWireless.length > 0
                                text: "UNPAIRED WIRELESS DEVICES"
                                font.letterSpacing: 2; font.pixelSize: 11; opacity: 0.65
                            }
                            Label {
                                visible: root.unboundWireless.length > 0
                                text: "Pairing explicitly connects a device to this wireless controller. It preserves the device’s reported fan PWM values. Devices are never paired automatically."
                                Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12
                            }
                            Repeater {
                                model: root.unboundWireless
                                RowLayout {
                                    id: wirelessRow
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Label { text: wirelessRow.modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                                    RoundedButton {
                                        text: "Pair"
                                        enabled: !root.backend.busy
                                        Accessible.name: "Pair " + wirelessRow.modelData.name
                                        onClicked: root.backend.command(["pair", "--device", String(wirelessRow.modelData.device_id)], "pair")
                                    }
                                }
                            }
                            Label {
                                visible: root.backend.operation === "pair" && root.backend.busy
                                text: "Pairing device… Diagnostics refresh after pairing succeeds."
                                Layout.fillWidth: true; wrapMode: Text.Wrap
                            }
                            Repeater {
                                model: [{id: "openrgb", label: "OpenRGB"}, {id: "lianli", label: "Lian Li wireless RGB"}, {id: "kingston", label: "Kingston DDR5 detection"}]
                                RowLayout {
                                    id: componentRow
                                    required property var modelData
                                    Layout.fillWidth: true
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Label { text: componentRow.modelData.label }
                                        Label {
                                            text: {
                                                var components = root.backend.diagnostics && root.backend.diagnostics.components ? root.backend.diagnostics.components : root.backend.state.setup
                                                var component = components ? components[componentRow.modelData.id] : null
                                                return component ? (component.available ? "Available" : "Setup required") : "Run diagnostics to check"
                                            }
                                            opacity: 0.6; font.pixelSize: 11
                                        }
                                    }
                                    RoundedButton { text: "Set up"; enabled: !root.backend.busy; onClicked: root.setup(componentRow.modelData.id) }
                                }
                            }
                            RowLayout {
                                RoundedButton { text: "Set up all components"; enabled: !root.backend.busy; onClicked: root.setup("all") }
                                RoundedButton { text: "Restore lighting"; enabled: !root.backend.busy; onClicked: root.backend.command(["restore"]) }
                            }
                            Label { visible: root.backend.operation === "setup" && root.backend.busy; text: "Setup is running. Keep this panel open to see the result."; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Label { visible: root.backend.diagnostics !== null; text: "DETAILS"; font.pixelSize: 11; opacity: 0.65; font.letterSpacing: 2 }
                            TextArea {
                                visible: root.backend.diagnostics !== null
                                Layout.fillWidth: true
                                readOnly: true
                                selectByMouse: true
                                text: root.backend.diagnostics ? JSON.stringify(root.backend.diagnostics, null, 2) : ""
                                textFormat: Text.PlainText
                                wrapMode: Text.Wrap
                                font.family: "monospace"; font.pixelSize: 10
                            }
                        }
                    }
                }
            }
        }
    }
}
