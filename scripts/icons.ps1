# Export browser sizes from the current artwork, with a flat printed mark and exterior tile shadow.
Add-Type -AssemblyName System.Drawing
$folioRoot = Split-Path -Parent $PSScriptRoot
$folioSource = [System.Drawing.Image]::FromFile((Join-Path $folioRoot 'design/folio-icon.png'))
try {
    foreach ($folioSize in @(16, 32, 48, 128, 256)) {
        $folioBitmap = [System.Drawing.Bitmap]::new($folioSize, $folioSize)
        $folioGraphics = [System.Drawing.Graphics]::FromImage($folioBitmap)
        $folioAttributes = [System.Drawing.Imaging.ImageAttributes]::new()
        try {
            $folioGraphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
            $folioGraphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
            $folioGraphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $folioGraphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $folioAttributes.SetWrapMode([System.Drawing.Drawing2D.WrapMode]::TileFlipXY)
            $folioRect = [System.Drawing.Rectangle]::new(0, 0, $folioSize, $folioSize)
            $folioGraphics.DrawImage($folioSource, $folioRect, 0, 0, $folioSource.Width, $folioSource.Height, [System.Drawing.GraphicsUnit]::Pixel, $folioAttributes)
            $folioBitmap.Save((Join-Path $folioRoot "icons/$folioSize.png"), [System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $folioAttributes.Dispose()
            $folioGraphics.Dispose()
            $folioBitmap.Dispose()
        }
    }
} finally { $folioSource.Dispose() }
