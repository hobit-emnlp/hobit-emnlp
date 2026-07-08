$ErrorActionPreference = "Stop"

Write-Host "Checking backend health..."
$health = Invoke-RestMethod -Uri "http://localhost:8000/health"
if ($health.status -ne "ok") {
  throw "Backend health check failed"
}

$headers = @{ "X-Session-ID" = "verify-demo" }
$body = @{ question = "졸업요건 알려줘"; language = "KO" } | ConvertTo-Json
$first = Invoke-RestMethod -Uri "http://localhost:8000/api/v0/question" -Method POST -Headers $headers -ContentType "application/json" -Body $body
if (-not $first.needs_profile) {
  throw "Expected the first graduation query to request profile fields"
}

$profile = @{ department = "컴퓨터학과"; admission_year = 20; language = "KO" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/v0/profile" -Method POST -Headers $headers -ContentType "application/json" -Body $profile | Out-Null

$second = Invoke-RestMethod -Uri "http://localhost:8000/api/v0/question" -Method POST -Headers $headers -ContentType "application/json" -Body $body
if (-not $second.faqs -or $second.faqs.Count -lt 1) {
  throw "Expected a profile-conditioned answer"
}

Write-Host "Demo verification passed."
