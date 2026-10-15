import QtQuick
import QtTest
import QtQuick.Controls
import ".." as Zorya

TestCase {
    name: "ZoryaColorWheel"
    width: 240
    height: 500
    visible: true
    when: windowShown
    Zorya.ColorWheel {
        id: wheel
        width: 224
        height: 224
        onColorPicked: function(value) { selectedColor = value }
    }
    ScrollView {
        x: 0; y: 250; width: 240; height: 240
        contentWidth: 240; contentHeight: 700
        Zorya.ColorWheel {
            id: scrollWheel; width: 224; height: 224
            onColorPicked: function(value) { selectedColor = value }
        }
    }
    SignalSpy { id: scrolledPicked; target: scrollWheel; signalName: "colorPicked" }
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
    function test_scrollview_does_not_steal_continuous_drag() {
        scrolledPicked.clear()
        mousePress(scrollWheel, 170, 170)
        for (var y = 150; y >= 50; y -= 20) mouseMove(scrollWheel, 160, y, 30)
        mouseRelease(scrollWheel, 160, 50)
        verify(scrolledPicked.count >= 7, "ScrollView interrupted wheel drag after " + scrolledPicked.count + " colors")
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
