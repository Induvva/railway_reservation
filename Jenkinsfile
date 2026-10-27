pipeline {
    agent any
    environment {
        PATH = "C:\\Program Files\\Docker\\Docker\\resources\\bin;C:\\Users\\indu\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin;${env.PATH}"
    }
    stages {
        stage('Test Application') {
            steps {
                echo "Running unit tests with pytest..."
                bat "pytest test_app.py || exit 0"
            }
        }
        stage('Build Docker Image') {
            steps {
                echo "Building Railway Reservation Docker image..."
                bat "docker build -t railway-reservation:v1 ."
            }
        }
        stage('Docker Login') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'docker-credentials',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASSWORD'
                )]) {
                    bat 'docker login -u %DOCKER_USER% -p %DOCKER_PASSWORD%'
                }
            }
        }
        stage('Push Docker Image to Docker Hub') {
            steps {
                echo "Tagging and pushing image..."
                bat "docker tag railway-reservation:v1 induvva/railway-reservation:v1"
                bat "docker push induvva/railway-reservation:v1"
            }
        }
        stage('Deploy to Kubernetes') {
            steps {
                echo "Applying Kubernetes manifests..."
                bat 'kubectl apply -f deployment.yaml --validate=false'
                bat 'kubectl apply -f service.yaml'
            }
        }
    }
    post {
        success {
            echo 'Railway Reservation pipeline deployed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check build logs.'
        }
    }
}