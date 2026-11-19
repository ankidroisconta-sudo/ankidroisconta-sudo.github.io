param([string]$InputFile, [string]$OutputFile)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$spec = Get-Content -LiteralPath $InputFile -Raw -Encoding UTF8 | ConvertFrom-Json
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    if ($spec.voice) { $speaker.SelectVoice($spec.voice) }
    else { $speaker.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet, [System.Speech.Synthesis.VoiceAge]::NotSet, 0, [System.Globalization.CultureInfo]::GetCultureInfo('pt-BR')) }
    $speaker.SetOutputToWaveFile($OutputFile)
    $speaker.Speak([string]$spec.text)
} finally { $speaker.Dispose() }
