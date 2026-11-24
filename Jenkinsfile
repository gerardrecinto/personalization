// Jenkins pipeline: test, build, scan, deploy, undo on failure. Same steps as .github/workflows/ci.yml.
// Not run on a Jenkins server.
pipeline {
  agent any
  options { timeout(time: 25, unit: 'MINUTES'); disableConcurrentBuilds() }
  environment { IMAGE = "registry.example.com/personalization-lab:${env.GIT_COMMIT}" }
  stages {
    stage('Unit tests') { steps { sh 'pip install -r requirements-dev.txt && pytest tests/test_unit.py' } }
    stage('Build') { steps { sh 'docker build -t "$IMAGE" .' } }
    stage('Scan') { steps { sh 'trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 "$IMAGE"' } }
    stage('Deploy') {
      steps {
        sh '''
          kubectl apply -f k8s/lab.yaml
          kubectl set image deployment/api api="$IMAGE" && kubectl set image deployment/worker worker="$IMAGE"
          kubectl rollout status deployment/api --timeout=120s
        '''
      }
    }
  }
  post { failure { sh 'kubectl rollout undo deployment/api || true' } }
}
