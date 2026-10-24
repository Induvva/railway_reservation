pipeline {
    agent any

    triggers {
        pollSCM('* * * * *')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        stage('Install Dependencies') {
            steps {
                bat 'python -m venv venv'
                bat 'venv\\Scripts\\python -m pip install -r requirements.txt'
            }
        }
        stage('Test') {
            steps {
                bat 'venv\\Scripts\\python -m pytest -v'
            }
        }
        stage('Build') {
            steps {
                echo 'Build successful'
                archiveArtifacts artifacts: 'app.py, templates/**, static/**', fingerprint: true
            }
        }
        stage('Deploy') {
            steps {
                bat 'if not exist C:\\railway-deploy mkdir C:\\railway-deploy'
                bat 'xcopy /E /I /Y . C:\\railway-deploy'
                echo 'Deployed to C:\\railway-deploy'
            }
        }
    }

    post {
        success { echo 'Pipeline succeeded' }
        failure { echo 'Pipeline failed, check the console output' }
    }
}