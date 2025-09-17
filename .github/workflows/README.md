# GitHub Actions CI/CD Setup Guide

이 문서는 Datadog Runner 프로젝트의 GitHub Actions CI/CD 파이프라인 설정 가이드입니다.

## 🚀 워크플로우 개요

### 단일 워크플로우 구조
- **main 브랜치 푸시 시 자동 배포**: 빌드 → ECR 푸시 → EKS 배포
- **수동 배포 지원**: workflow_dispatch를 통한 버전 지정 배포
- **단일 환경**: default 네임스페이스에 배포

## 🔧 필수 설정

### GitHub Secrets 설정

Repository Settings → Secrets and variables → Actions에서 다음 secrets를 설정하세요:

#### AWS 관련 Secrets
```
AWS_ACCESS_KEY_ID          # AWS 액세스 키 ID
AWS_SECRET_ACCESS_KEY      # AWS 시크릿 액세스 키
```

### AWS IAM 권한

GitHub Actions에서 사용할 IAM 사용자에게 다음 권한이 필요합니다:

#### ECR 관련 권한
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:BatchImportLayerPart",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
                "ecr:PutImage",
                "ecr:CreateRepository",
                "ecr:DescribeRepositories"
            ],
            "Resource": "*"
        }
    ]
}
```

#### EKS 관련 권한
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "eks:DescribeCluster",
                "eks:ListClusters",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

## 🔄 워크플로우 트리거

### 자동 트리거
- **main 브랜치 푸시** → 자동 빌드 및 배포

### 수동 트리거
1. Actions 탭 → "Build and Deploy to EKS" 선택
2. "Run workflow" 클릭
3. 원하는 버전 태그 입력 후 실행 (선택사항)

## 📋 사전 요구사항

### EKS 클러스터 생성
워크플로우 실행 전에 다음 스크립트로 EKS 클러스터를 생성하세요:

```bash
# EKS 클러스터 생성
./scripts/create-eks-cluster.sh datadog-runner
```

### EKS 클러스터에 IAM 권한 추가

```bash
# 클러스터 연결
aws eks update-kubeconfig --region us-east-1 --name datadog-runner

# aws-auth ConfigMap 편집
kubectl edit configmap aws-auth -n kube-system
```

ConfigMap에 GitHub Actions IAM 사용자 추가:
```yaml
mapUsers: |
  - userarn: arn:aws:iam::YOUR_ACCOUNT_ID:user/YOUR_IAM_USER_NAME
    username: github-actions-user
    groups:
      - system:masters
```

## 🚀 사용법

### 자동 배포
```bash
git add .
git commit -m "feat: new feature"
git push origin main
```

### 수동 배포
1. Actions 탭에서 "Build and Deploy to EKS" 선택
2. "Run workflow" 클릭
3. 버전 태그 입력 (예: v1.0.0) 또는 비워두고 자동 생성
4. "Run workflow" 실행

## 📊 배포 상태 확인

```bash
# EKS 클러스터 연결
aws eks update-kubeconfig --region us-east-1 --name datadog-runner

# 배포 상태 확인
kubectl get pods
kubectl get services
kubectl get ingress
```

## 🐛 트러블슈팅

### 일반적인 문제들

#### 1. AWS 권한 오류
```
Error: The security token included in the request is invalid
```
**해결방법**: AWS_ACCESS_KEY_ID와 AWS_SECRET_ACCESS_KEY를 다시 확인하세요.

#### 2. EKS 클러스터 접근 오류
```
Error: You must be logged in to the server (Unauthorized)
```
**해결방법**: EKS 클러스터의 aws-auth ConfigMap에 IAM 사용자를 추가하세요.

#### 3. ECR 권한 오류
```
Error: no basic auth credentials
```
**해결방법**: ECR 관련 IAM 권한을 확인하세요.

## 🔄 롤백 방법

### 이전 워크플로우 재실행
1. Actions 탭에서 성공한 이전 워크플로우 선택
2. "Re-run jobs" 클릭

### 수동 롤백
```bash
# 특정 버전으로 롤백
kubectl set image deployment/auth-python auth-python=<ECR_URI>:<OLD_VERSION>
kubectl set image deployment/chat-node chat-node=<ECR_URI>:<OLD_VERSION>
kubectl set image deployment/ranking-java ranking-java=<ECR_URI>:<OLD_VERSION>
kubectl set image deployment/frontend frontend=<ECR_URI>:<OLD_VERSION>
```

## 📝 추가 정보

- 모든 이미지는 `linux/amd64` 플랫폼으로 빌드됩니다
- ECR 리포지토리는 자동으로 생성됩니다
- 캐싱을 통해 빌드 시간을 최적화합니다
- 배포는 순차적으로 진행됩니다 (인프라 → 애플리케이션 → 프론트엔드 → Ingress)
- default 네임스페이스에 모든 리소스가 배포됩니다