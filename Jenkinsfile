pipeline {
    agent any

    environment {
        PYTHON = 'C:\\Users\\duvva\\AppData\\Local\\Programs\\Python\\Python313\\python.exe'
    }
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
                bat '"%PYTHON%" -m venv venv'
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
                bat 'xcopy /E /I /Y templates C:\\railway-deploy\\templates'
                bat 'xcopy /E /I /Y static C:\\railway-deploy\\static'
                bat 'copy /Y app.py C:\\railway-deploy\\'
                bat 'copy /Y requirements.txt C:\\railway-deploy\\'
                echo 'Deployed to C:\\railway-deploy'
            }
        }
    }

    post {
        success { echo 'Pipeline succeeded' }
        failure { echo 'Pipeline failed, check the console output' }
    }
}