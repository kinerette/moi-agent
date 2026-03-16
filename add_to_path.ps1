$binDir = "C:\Users\palfi\bin"
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$binDir", "User")
    Write-Host "Added $binDir to PATH. Restart your terminal."
} else {
    Write-Host "$binDir already in PATH."
}
