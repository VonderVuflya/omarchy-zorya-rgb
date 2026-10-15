import QtQuick
import QtTest
import ".." as Zorya

TestCase {
    name: "ZoryaColorWheel"
    width: 240
    height: 240
    visible: true
    when: windowShown
    Zorya.ColorWheel {
        id: wheel
        width: 224
        height: 224
        onColorPicked: function(value) { selectedColor = value }
    }
    SignalSpy { id: picked; target: wheel; signalName: "colorPicked" }
    function init() { wheel.selectedColor = "#FFFFFF"; picked.clear() }
    function test_white_center_and_drag() {
        mousePress(wheel, 218, 112)
        verify(wheel.selectedColor !== "#FFFFFF")
        mouseMove(wheel, 112, 112, 20)
        mouseRelease(wheel, 112, 112)
        compare(wheel.selectedColor, "#FFFFFF")
        verify(picked.count >= 2)
    }
    function test_keyboard_white_and_hue() {
        wheel.selectedColor = "#FF0000"
        wheel.forceActiveFocus()
        keyClick(Qt.Key_Right)
        verify(wheel.selectedColor !== "#FF0000")
        keyClick(Qt.Key_Home)
        compare(wheel.selectedColor, "#FFFFFF")
        keyClick(Qt.Key_Up)
        verify(wheel.selectedColor !== "#FFFFFF")
    }
}
