Write-Host "Getting access to ACR: $(ACR)"
docker login -u "$(ACR_username)" -p "$(ACR_password)" "$(ACR)"

Write-Host "Building latest image"
cd alexmcq99_discord-bot
$latest="$(ACR)/discord-music-bot:latest"
docker build -t $latest .

Write-Host "Pushing latest image"
docker push $latest