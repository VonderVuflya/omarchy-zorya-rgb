.pragma library

function clamp(value, low, high) { return Math.min(high, Math.max(low, value)) }
function normalizeHex(value) {
    var text = String(value).trim().toUpperCase()
    if (/^[0-9A-F]{6}$/.test(text)) text = "#" + text
    return /^#[0-9A-F]{6}$/.test(text) ? text : null
}
function rgb(hex) {
    var text = normalizeHex(hex) || "#FFFFFF"
    return [parseInt(text.slice(1, 3), 16), parseInt(text.slice(3, 5), 16), parseInt(text.slice(5, 7), 16)]
}
function fromRgb(red, green, blue) {
    var values = [red, green, blue]
    for (var i = 0; i < values.length; ++i)
        if (!Number.isFinite(Number(values[i])) || Number(values[i]) < 0 || Number(values[i]) > 255) return null
    return "#" + values.map(function(v) { return Math.round(Number(v)).toString(16).padStart(2, "0") }).join("").toUpperCase()
}
function hsv(hex) {
    var values = rgb(hex).map(function(v) { return v / 255 })
    var maximum = Math.max.apply(null, values), minimum = Math.min.apply(null, values)
    var delta = maximum - minimum, hue = 0
    if (delta > 0) {
        if (maximum === values[0]) hue = ((values[1] - values[2]) / delta) % 6
        else if (maximum === values[1]) hue = (values[2] - values[0]) / delta + 2
        else hue = (values[0] - values[1]) / delta + 4
        hue = (hue / 6 + 1) % 1
    }
    return {h: hue, s: maximum === 0 ? 0 : delta / maximum, v: maximum}
}
function fromHsv(hue, saturation, value) {
    hue = ((hue % 1) + 1) % 1
    saturation = clamp(saturation, 0, 1)
    value = clamp(value, 0, 1)
    var sector = Math.floor(hue * 6), fraction = hue * 6 - sector
    var p = value * (1 - saturation), q = value * (1 - fraction * saturation), t = value * (1 - (1 - fraction) * saturation)
    var colors = [[value,t,p], [q,value,p], [p,value,t], [p,q,value], [t,p,value], [value,p,q]]
    return fromRgb.apply(null, colors[sector % 6].map(function(v) { return Math.round(v * 255) }))
}
function pointColor(x, y, size) {
    var dx = x - size / 2, dy = y - size / 2
    return fromHsv((Math.atan2(dy, dx) / (2 * Math.PI) + 1) % 1, clamp(Math.sqrt(dx * dx + dy * dy) / (size / 2), 0, 1), 1)
}
