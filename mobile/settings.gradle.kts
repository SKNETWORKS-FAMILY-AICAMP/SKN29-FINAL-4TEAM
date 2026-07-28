pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(
        RepositoriesMode.FAIL_ON_PROJECT_REPOS
    )

    repositories {
        google()
        mavenCentral()

        maven {
            url = uri(
                "https://devrepo.kakao.com/" +
                    "nexus/repository/" +
                    "kakaomap-releases/"
            )
        }
    }
}

rootProject.name = "WaterPurifierDealer"

include(":customerApp")
project(":customerApp").projectDir =
    file("app")

include(":technicianApp")
