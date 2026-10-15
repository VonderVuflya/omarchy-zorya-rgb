import QtQuick
import "ColorModel.js" as Colors

Item {
    id: wheel
    implicitWidth: 224
    implicitHeight: 224
    property string selectedColor: "#FFFFFF"
    readonly property var hsv: Colors.hsv(selectedColor)
    signal colorPicked(string value)
    activeFocusOnTab: true
    Accessible.role: Accessible.Slider
    Accessible.name: "Color wheel. Left and right adjust hue; up and down adjust saturation; Home selects white."
    Accessible.description: selectedColor

    Canvas {
        id: canvas
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var radius = Math.min(width, height) / 2 - 5
            ctx.translate(width / 2, height / 2)
            for (var i = 0; i < 180; ++i) {
                var start = i / 180 * 2 * Math.PI, end = (i + 1.5) / 180 * 2 * Math.PI
                var gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, radius)
                gradient.addColorStop(0, "#FFFFFF")
                gradient.addColorStop(1, Colors.fromHsv(i / 180, 1, 1))
                ctx.fillStyle = gradient
                ctx.beginPath(); ctx.moveTo(0, 0); ctx.arc(0, 0, radius, start, end); ctx.closePath(); ctx.fill()
            }
        }
    }
    Rectangle {
        width: 16; height: 16; radius: 8
        x: wheel.width / 2 + Math.cos(wheel.hsv.h * Math.PI * 2) * wheel.hsv.s * (wheel.width / 2 - 5) - width / 2
        y: wheel.height / 2 + Math.sin(wheel.hsv.h * Math.PI * 2) * wheel.hsv.s * (wheel.height / 2 - 5) - height / 2
        color: wheel.selectedColor
        border.width: wheel.activeFocus ? 3 : 2
        border.color: "#20242D"
    }
    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.CrossCursor
        function pick(mouse) {
            wheel.forceActiveFocus()
            var size = Math.min(wheel.width, wheel.height) - 10
            wheel.colorPicked(Colors.pointColor(mouse.x - 5, mouse.y - 5, size))
        }
        onPressed: function(mouse) { pick(mouse) }
        onPositionChanged: function(mouse) { if (pressed) pick(mouse) }
    }
    Keys.onPressed: function(event) {
        var h = wheel.hsv.h, s = wheel.hsv.s
        if (event.key === Qt.Key_Home) wheel.colorPicked("#FFFFFF")
        else if (event.key === Qt.Key_Left) wheel.colorPicked(Colors.fromHsv(h - 1 / 72, s, 1))
        else if (event.key === Qt.Key_Right) wheel.colorPicked(Colors.fromHsv(h + 1 / 72, s, 1))
        else if (event.key === Qt.Key_Up) wheel.colorPicked(Colors.fromHsv(h, s + 0.02, 1))
        else if (event.key === Qt.Key_Down) wheel.colorPicked(Colors.fromHsv(h, s - 0.02, 1))
        else return
        event.accepted = true
    }
}
