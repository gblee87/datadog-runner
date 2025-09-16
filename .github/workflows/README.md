# GitHub Actions CI/CD Setup Guide

이 문서는 Datadog Runner 프로젝트의 GitHub Actions CI/CD 파이프라인 설정 가이드입니다.

## 🚀 워크플로우 개요

### 1. Build Job
- 모든 서비스의 Docker 이미지를 빌드하고 ECR에 푸시
- 버전 태깅 (main 브랜치: `v20231215-abc1234`, develop 브랜치: `dev-abc1234`)
- 캐싱을 통한 빌드 시간 최적화

### 2. Deploy Jobs
- **Staging**: develop 브랜치 푸시 시 자동 배포
- **Production**: main 브랜치 푸시 시 자동 배포
- 수동 배포도 지원 (workflow_dispatch)

## 🔧 필수 설정

### GitHub Secrets 설정

Repository Settings → Secrets and variables → Actions에서 다음 secrets를 설정하세요:

#### AWS 관련 Secrets
```
AWS_ACCESS_KEY_ID          # AWS 액세스 키 ID
AWS_SECRET_ACCESS_KEY      # AWS 시크릿 액세스 키
```

#### EKS 클러스터 관련 정보
단일 EKS 클러스터를 사용하며, staging과 production은 네임스페이스로 분리됩니다.
클러스터 이름은 워크플로우에서 `datadog-runner`로 하드코딩되어 있습니다.

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
                "eks:ListClusters"
            ],
            "Resource": "*"
        }
    ]
}
```

#### STS 권한
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

## 🎯 Environment 설정

### Staging Environment
- Repository Settings → Environments → New environment
- Name: `staging`
- Protection rules (선택사항):
  - Required reviewers 설정 가능

### Production Environment
- Repository Settings → Environments → New environment
- Name: `production`
- Protection rules (권장):
  - Required reviewers: 1명 이상
  - Wait timer: 5분 (선택사항)

## 🔄 워크플로우 트리거

### 자동 트리거
1. **develop 브랜치 푸시** → Staging 배포
2. **main 브랜치 푸시** → Production 배포
3. **Pull Request** → 빌드만 실행 (배포 안함)

### 수동 트리거
1. Actions 탭 → "Build and Deploy to EKS" 선택
2. "Run workflow" 클릭
3. 환경과 버전 선택 후 실행

## 📋 사전 요구사항

### EKS 클러스터 생성
워크플로우 실행 전에 다음 스크립트로 단일 EKS 클러스터를 생성하세요:

```bash
# 단일 클러스터 생성 (staging과 production은 네임스페이스로 분리)
./scripts/create-eks-cluster.sh datadog-runner
```

### Datadog Agent 설치 (선택사항)
```bash
# 스테이징 환경
./scripts/install-datadog.sh staging

# 프로덕션 환경
./scripts/install-datadog.sh production
```

## 🐛 트러블슈팅

### 일반적인 문제들

#### 1. ECR 로그인 실패
- AWS credentials 확인
- ECR 권한 확인
- AWS 리전 설정 확인

#### 2. EKS 클러스터 접근 실패
- 클러스터 이름 확인
- kubectl 권한 확인
- 클러스터 상태 확인

#### 3. 이미지 태그 업데이트 실패
- manifest 파일 경로 확인
- sed 명령어 패턴 확인

### 로그 확인 방법
1. Actions 탭에서 실패한 워크플로우 클릭
2. 실패한 Job 클릭
3. 실패한 Step 클릭하여 상세 로그 확인

## 📊 모니터링

### 배포 상태 확인
```bash
# 스테이징 환경
kubectl get pods -n staging
kubectl get services -n staging
kubectl get ingress -n staging

# 프로덕션 환경
kubectl get pods -n production
kubectl get services -n production
kubectl get ingress -n production
```

### Datadog 모니터링
- 배포된 애플리케이션은 자동으로 Datadog에 메트릭과 로그 전송
- Datadog 대시보드에서 실시간 모니터링 가능

## 🔄 롤백 방법

### 이전 버전으로 롤백
```bash
# 이전 이미지 태그로 수동 업데이트
kubectl set image deployment/auth-python auth-python=<ECR_URI>:<OLD_VERSION> -n <NAMESPACE>
kubectl set image deployment/chat-node chat-node=<ECR_URI>:<OLD_VERSION> -n <NAMESPACE>
kubectl set image deployment/ranking-java ranking-java=<ECR_URI>:<OLD_VERSION> -n <NAMESPACE>
kubectl set image deployment/frontend frontend=<ECR_URI>:<OLD_VERSION> -n <NAMESPACE>
```

### 또는 이전 워크플로우 재실행
1. Actions 탭에서 성공한 이전 워크플로우 선택
2. "Re-run jobs" 클릭

## 📝 추가 정보

- 모든 이미지는 `linux/amd64` 플랫폼으로 빌드됩니다
- ECR 리포지토리는 자동으로 생성됩니다
- 캐싱을 통해 빌드 시간을 최적화합니다
- 배포는 순차적으로 진행됩니다 (인프라 → 애플리케이션 → 프론트엔드 → Ingress)
