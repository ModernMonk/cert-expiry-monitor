pipeline {
    agent { label 'WODC Jenkins Agent 17043' }

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

        stage('Validate Prerequisites') {
            steps {
                script {
                    // Check if input file exists
                    if (!fileExists("${INPUT_FILE}")) {
                        error("Required input file '${INPUT_FILE}' not found in workspace")
                    }
                    
                    // Check if Docker is available
                    sh 'docker --version'
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    docker.build(DOCKER_IMAGE)
                }
            }
        }

        stage('Prepare Reports Directory') {
            steps {
                script {
                    sh 'mkdir -p ${REPORTS_DIR}'
                    sh 'chmod 777 ${REPORTS_DIR}'
                }
            }
        }

        stage('Run Certificate Check in Docker') {
            steps {
                script {
                    def workspaceDir = pwd()
                    
                    try {
                        docker.image(DOCKER_IMAGE).inside("-v ${workspaceDir}/${REPORTS_DIR}:/app/reports -v ${workspaceDir}/${INPUT_FILE}:/app/${INPUT_FILE}:ro") {
                            sh '''
                                python cert_monitor.py --input ${INPUT_FILE} --output-dir ${REPORTS_DIR}
                                
                                # Verify output files were created
                                if [ ! -f "${REPORTS_DIR}/certificate_report.html" ]; then
                                    echo "ERROR: certificate_report.html was not generated"
                                    exit 1
                                fi
                            '''
                        }
                    } catch (Exception e) {
                        error("Certificate monitoring job failed: ${e.message}")
                    }
                }
            }
        }

        stage('Verify Report Generation') {
            steps {
                script {
                    if (!fileExists("${REPORTS_DIR}/certificate_report.html")) {
                        error("certificate_report.html not found after Docker execution")
                    }
                    if (!fileExists("${REPORTS_DIR}/certificate_report.json")) {
                        error("certificate_report.json not found after Docker execution")
                    }
                    
                    echo "✓ All required reports generated successfully"
                }
            }
        }

        stage('Archive Reports') {
            steps {
                archiveArtifacts(
                    artifacts: '${REPORTS_DIR}/*',
                    fingerprint: true,
                    allowEmptyArchive: false
                )
            }
        }

        stage('Send Email Report') {
            when {
                allOf {
                    expression { env.EMAIL_RECIPIENTS?.trim() }
                    fileExists("${REPORTS_DIR}/certificate_report.html")
                }
            }
            steps {
                script {
                    try {
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
                        echo "✓ Email report sent successfully to: ${env.EMAIL_RECIPIENTS}"
                    } catch (Exception e) {
                        echo "⚠ Failed to send email report: ${e.message}"
                        // Don't fail the build, just warn
                    }
                }
            }
        }
    }

    post {
        always {
            script {
                // Copy reports to a persistent location before cleanup (optional)
                // sh 'cp -r ${REPORTS_DIR} /var/jenkins_reports/${BUILD_NUMBER} || true'
                
                cleanWs()
            }
        }
        failure {
            script {
                if (env.ADMIN_EMAIL?.trim()) {
                    try {
                        emailext(
                            subject: "SSL Certificate Check FAILED - ${new Date().format('yyyy-MM-dd')}",
                            body: """
                                The certificate monitoring job failed.
                                
                                Build: ${env.BUILD_URL}
                                Job: ${env.JOB_NAME}
                                Build Number: ${env.BUILD_NUMBER}
                                
                                Please review the Jenkins console output for details.
                            """,
                            to: env.ADMIN_EMAIL
                        )
                    } catch (Exception e) {
                        echo "Failed to send failure email: ${e.message}"
                    }
                }
            }
        }
        success {
            echo "✓ SSL Certificate Expiry Monitor completed successfully"
        }
    }
}
