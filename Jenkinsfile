pipeline {
    agent { label 'permanent-docker' }

    triggers {
        cron('H 8 * * *')
    }

    environment {
        REPORTS_DIR = 'reports'
        INPUT_FILE = 'certificates.txt'
        DOCKER_IMAGE = 'cert-monitor:latest'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    docker.build(DOCKER_IMAGE)
                }
            }
        }

        stage('Run Certificate Check in Docker') {
            steps {
                script {
                    def workspaceDir = pwd()
                    docker.image(DOCKER_IMAGE).inside("-v ${workspaceDir}/${REPORTS_DIR}:/app/reports") {
                        sh '''
                            mkdir -p reports
                            python cert_monitor.py --input ${INPUT_FILE} --output-dir ${REPORTS_DIR}
                        '''
                    }
                }
            }
        }

        stage('Archive Reports') {
            steps {
                archiveArtifacts artifacts: '${REPORTS_DIR}/*', fingerprint: true
            }
        }

        stage('Send Email Report') {
            when {
                expression { env.EMAIL_RECIPIENTS?.trim() }
            }
            steps {
                script {
                    def htmlReport = readFile("${REPORTS_DIR}/certificate_report.html")

                    emailext(
                        subject: "SSL Certificate Expiry Report - ${new Date().format('yyyy-MM-dd')}",
                        body: """
                            <p>Please find the SSL certificate expiry report attached.</p>
                            <p>Generated at: ${new Date().format('yyyy-MM-dd HH:mm:ss')}</p>
                            <br/>
                            ${htmlReport}
                        """,
                        mimeType: 'text/html',
                        to: env.EMAIL_RECIPIENTS,
                        attachmentsPattern: "${REPORTS_DIR}/certificate_report.json,${REPORTS_DIR}/certificate_report.html"
                    )
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
        failure {
            script {
                if (env.ADMIN_EMAIL?.trim()) {
                    emailext(
                        subject: "SSL Certificate Check FAILED - ${new Date().format('yyyy-MM-dd')}",
                        body: "The certificate monitoring job failed. Please review the Jenkins console output.",
                        to: env.ADMIN_EMAIL
                    )
                }
            }
        }
    }
}